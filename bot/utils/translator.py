import asyncio
import logging
from typing import Dict, Tuple
import httpx
import bs4

logger = logging.getLogger(__name__)

# Cache en memoria para traducciones instantáneas: (text, target_lang) -> translated_text
_TRANSLATION_CACHE: Dict[Tuple[str, str], str] = {}

# Patrones típicos de páginas de error devueltas por scrapers bloqueados
ERROR_PATTERNS = [
    "error 500",
    "server error",
    "1500.that",
    "that's an error",
    "that’s an error",
    "please try again later",
    "that's all we know",
    "that’s all we know",
    "429 too many requests",
    "too many requests",
    "rate limit",
    "<!doctype",
    "<html"
]

def is_error_translation(translated: str) -> bool:
    """Verifica si la respuesta obtenida es en realidad una página de error o bloqueo de Google"""
    if not translated or not translated.strip():
        return True
    lower = translated.lower()
    return any(pattern in lower for pattern in ERROR_PATTERNS)

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,pt;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

async def translate_text(text: str, target_lang: str = "es") -> str:
    """
    Traduce un texto dinámico (notas del admin, términos o descripciones de productos)
    al idioma configurado de forma asíncrona, con caché y protección estricta contra errores 500 de Google.
    """
    if not text or not text.strip():
        return text

    target_lang = (target_lang or "es").lower().strip()
    if target_lang not in ["es", "en", "pt"]:
        target_lang = "es"

    cleaned_text = text.strip()

    # Si el idioma destino es inglés y el texto original ya está en inglés, retornar directo
    if target_lang == "en":
        return cleaned_text

    cache_key = (cleaned_text, target_lang)
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    # 1. Intento primario: Solicitud asíncrona directa con headers reales de navegador
    try:
        url = "https://translate.google.com/m"
        params = {"sl": "auto", "tl": target_lang, "q": cleaned_text}
        async with httpx.AsyncClient(headers=_BROWSER_HEADERS, timeout=5.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                soup = bs4.BeautifulSoup(resp.text, "html.parser")
                elem = soup.find("div", {"class": "result-container"}) or soup.find("div", {"class": "t0"})
                if elem:
                    translated = elem.get_text().strip()
                    if translated and not is_error_translation(translated):
                        _TRANSLATION_CACHE[cache_key] = translated
                        return translated
    except Exception as e:
        logger.warning(f"Aviso: Fallo en traducción directa httpx ({target_lang}): {e}")

    # 2. Intento secundario: deep_translator validado
    try:
        from deep_translator import GoogleTranslator
        translated = await asyncio.to_thread(
            lambda: GoogleTranslator(source="auto", target=target_lang).translate(cleaned_text)
        )
        if translated and not is_error_translation(translated):
            _TRANSLATION_CACHE[cache_key] = translated
            return translated
    except Exception as e:
        logger.warning(f"Aviso: Fallo en fallback deep_translator ({target_lang}): {e}")

    # 3. Fallback de seguridad: Si no se pudo traducir o devolvió error, retornar texto original limpio
    return cleaned_text
