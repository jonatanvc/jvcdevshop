import asyncio
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Cache en memoria para traducciones instantáneas: (text, target_lang) -> translated_text
_TRANSLATION_CACHE: Dict[Tuple[str, str], str] = {}

def _sync_translate(text: str, target_lang: str) -> str:
    """Ejecuta la traducción de manera síncrona usando deep_translator"""
    try:
        from deep_translator import GoogleTranslator
        # deep-translator soporta es, en, pt
        lang_code = target_lang.lower().strip()
        if lang_code not in ["es", "en", "pt"]:
            lang_code = "es"
            
        translated = GoogleTranslator(source="auto", target=lang_code).translate(text)
        return translated if translated else text
    except Exception as e:
        logger.warning(f"Error al traducir texto a {target_lang}: {e}")
        return text

async def translate_text(text: str, target_lang: str = "es") -> str:
    """
    Traduce un texto dinámico (como notas del admin o términos del producto)
    al idioma configurado por el usuario de forma asíncrona, con caché y tolerancia a fallos.
    """
    if not text or not text.strip():
        return text

    target_lang = (target_lang or "es").lower().strip()
    cache_key = (text.strip(), target_lang)

    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    try:
        # Ejecutar en thread separado con timeout para nunca bloquear el bot
        translated = await asyncio.wait_for(
            asyncio.to_thread(_sync_translate, text.strip(), target_lang),
            timeout=4.0
        )
        if translated:
            _TRANSLATION_CACHE[cache_key] = translated
            return translated
    except Exception as e:
        logger.warning(f"Timeout o fallo en traducción asíncrona: {e}")

    return text
