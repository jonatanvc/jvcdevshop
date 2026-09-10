import html
import re
from typing import Any, Dict, List, Union

def adjust_warranty_in_name(name: str) -> str:
    """
    Ajusta la garantía mostrada en el título del producto al 50%
    para que coincida exactamente con la garantía ofrecida por la tienda (50% de BunaiStore).
    Ejemplo:
      'Name: Netflix UHD PRIVATE (20 DAYS WARRANTY)' -> 'Netflix UHD PRIVATE (10 DAYS WARRANTY)'
      'Claude 100$ API 30DAYS (W10D)' -> 'Claude 100$ API 30DAYS (W5D)'
      'Chatgpt Plus (12hr warranty)' -> 'Chatgpt Plus (6hr warranty)'
      'Veo3 (10d warranty)' -> 'Veo3 (5d warranty)'
    """
    if not name or not isinstance(name, str):
        return ""

    clean_name = name.strip()

    # 1. Quitar prefijo "Name: " si el proveedor lo envía
    if clean_name.lower().startswith("name:"):
        clean_name = clean_name[5:].strip()

    # 2. Código tipo (W10D), (W20D), (W24H), (W1D)
    def repl_w_code(m):
        prefix = m.group(1)  # 'W' o 'w'
        num = int(m.group(2))
        unit = m.group(3)    # 'D', 'd', 'H', 'h'
        if unit.upper() == 'D':
            if num == 1:
                return f"{prefix}12{'h' if unit.islower() else 'H'}"
            new_num = max(1, num // 2)
            return f"{prefix}{new_num}{unit}"
        elif unit.upper() == 'H':
            new_num = max(1, num // 2)
            return f"{prefix}{new_num}{unit}"
        return m.group(0)

    clean_name = re.sub(r'\b([Ww])(\d+)([Dd|Hh])\b', repl_w_code, clean_name)

    # 3. Patrón explícito de garantía: e.g. "20 DAYS WARRANTY", "10d warranty", "24hr warranty", "15d warranty", "20 dias de garantia", etc.
    def repl_warranty(m):
        full = m.group(0)
        num_str = m.group(1)
        num = int(num_str)
        new_num = max(1, num // 2)
        return f"{new_num}{full[len(num_str):]}"

    clean_name = re.sub(
        r'\b(\d+)\s*(days?|dias?|días?|d|hours?|horas?|hr|hrs?|h)\s*(?:de\s*)?(warranty|garantia|garantía)\b',
        repl_warranty,
        clean_name,
        flags=re.IGNORECASE
    )

    # 4. Caso inverso: "warranty: 20 days", "garantia: 10 dias"
    def repl_inv_warranty(m):
        w_word = m.group(1)
        num_str = m.group(2)
        rest = m.group(3)
        new_num = max(1, int(num_str) // 2)
        return f"{w_word}: {new_num} {rest}"

    clean_name = re.sub(
        r'\b(warranty|garantia|garantía):\s*(\d+)\s*(days?|dias?|días?|d|hours?|horas?|hr|hrs?|h)\b',
        repl_inv_warranty,
        clean_name,
        flags=re.IGNORECASE
    )

    return clean_name


def format_single_credential_line(raw_line: str) -> str:
    """
    Formatea una línea individual de credenciales entregada por el proveedor.
    Soporta delimitadores '|' y ':' separando usuario, contraseña, 2FA, PIN o perfil.
    """
    line = raw_line.strip()
    if not line:
        return ""

    lower_line = line.lower()
    # Si ya tiene prefijos formateados, no re-procesar
    if any(lower_line.startswith(prefix) for prefix in ["usuario:", "user:", "email:", "correo:", "login:", "cuenta:"]):
        return line

    # 1. Si contiene tuberías '|' (formato estándar de cuentas digitales de BunaiStore)
    if "|" in line:
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            formatted = []
            formatted.append(f"Usuario: {parts[0]}")
            formatted.append(f"Password: {parts[1]}")

            for idx, extra in enumerate(parts[2:], start=3):
                extra_lower = extra.lower()
                if extra.isdigit() and len(extra) <= 6:
                    formatted.append(f"PIN: {extra}")
                elif any(k in extra_lower for k in ["2fa", "otp", "code", "authenticator"]) or re.match(r'^[A-Z2-7]{16,32}$', extra):
                    formatted.append(f"2FA: {extra}")
                elif "@" in extra and "." in extra:
                    formatted.append(f"Email Recuperación: {extra}")
                elif any(k in extra_lower for k in ["perfil", "profile", "pantalla", "screen"]):
                    formatted.append(f"Perfil: {extra}")
                else:
                    formatted.append(f"Dato {idx}: {extra}")
            return "\n".join(formatted)

    # 2. Si es formato correo:password (sin http)
    if ":" in line and not line.startswith("http://") and not line.startswith("https://"):
        colon_parts = line.split(":", 1)
        if len(colon_parts) == 2 and "@" in colon_parts[0] and " " not in colon_parts[0]:
            return f"Usuario: {colon_parts[0].strip()}\nPassword: {colon_parts[1].strip()}"

    # 3. Si es un enlace de invitación / activación
    if line.startswith("http://") or line.startswith("https://"):
        return f"Enlace: {line}"

    # 4. Si es una clave de licencia o token (ej: Windows retail key XXXX-XXXX-XXXX-XXXX o sk-...)
    if re.match(r'^[A-Z0-9]{4,5}(-[A-Z0-9]{4,5}){3,5}$', line) or line.startswith("sk-"):
        return f"Licencia / Key: {line}"

    # 5. Cualquier otro formato plano
    return line


def format_delivered_credentials(raw_input: Union[str, List[Any], Dict[str, Any]]) -> str:
    """
    Formatea las credenciales entregadas para que se visualicen ordenadas y claras:
      Usuario: <correo>
      Password: <contraseña>
      PIN / 2FA: <datos adicionales>

    Soporta compras individuales o múltiples (x2, x3, etc.) y es idempotente.
    """
    if not raw_input:
        return "OK"

    # Verificación de idempotencia si ya es texto formateado
    if isinstance(raw_input, str):
        cleaned_str = raw_input.strip()
        lower = cleaned_str.lower()
        if ("usuario:" in lower and "password:" in lower) or ("[cuenta " in lower):
            return cleaned_str

    lines = []
    if isinstance(raw_input, list):
        for item in raw_input:
            if isinstance(item, dict):
                content = item.get("content") or item.get("item") or item.get("credential") or item.get("data") or str(item)
                lines.append(str(content).strip())
            else:
                lines.append(str(item).strip())
    elif isinstance(raw_input, dict):
        content = raw_input.get("content") or raw_input.get("item") or raw_input.get("credential") or raw_input.get("data") or str(raw_input)
        lines = [str(content).strip()]
    elif isinstance(raw_input, str):
        lines = [l.strip() for l in raw_input.replace("\r\n", "\n").split("\n") if l.strip()]
    else:
        lines = [str(raw_input).strip()]

    # Filtrar vacíos
    lines = [l for l in lines if l]
    if not lines:
        return "OK"

    # Si sólo hay 1 línea/cuenta (caso más habitual)
    if len(lines) == 1:
        return format_single_credential_line(lines[0])

    # Si hay múltiples cuentas/ítems
    formatted_accounts = []
    account_num = 1
    for line in lines:
        # Omitir separadores ya existentes
        if re.match(r'^-{3,}.*-{3,}$', line) or re.match(r'^\[Cuenta \d+\]$', line):
            continue
        acc_formatted = format_single_credential_line(line)
        formatted_accounts.append(f"[Cuenta {account_num}]\n{acc_formatted}")
        account_num += 1

    return "\n\n".join(formatted_accounts)
