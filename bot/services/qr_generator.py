import os
import io
import qrcode
from typing import Union
from bot.config import settings

def get_wallet_qr_media() -> Union[str, io.BytesIO]:
    """
    Retorna la ruta al archivo de imagen estático de TrustWalletQR si existe,
    o genera una imagen QR en memoria (BytesIO) como respaldo.
    """
    # 1. Comprobar ruta configurada
    if settings.QR_IMAGE_PATH and os.path.isfile(settings.QR_IMAGE_PATH):
        return settings.QR_IMAGE_PATH

    # 2. Comprobar nombres alternativos comunes
    alternatives = [
        "assets/TrustWalletQR.jpg",
        "bot/TrustWalletQR.jpg",
        "assets/qr_wallet.png",
        "TrustWalletQR.jpg"
    ]
    for alt in alternatives:
        if os.path.isfile(alt):
            return alt

    # 3. Respaldo dinámico
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(settings.ADMIN_WALLET_BSC)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    bio.name = "qr_wallet.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio
