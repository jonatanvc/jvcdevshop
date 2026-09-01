from typing import Optional, Union, Dict
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, BadRequest, MessageIdInvalid

# Diccionario en memoria para rastrear el ID del único mensaje activo por usuario
USER_LAST_MESSAGES: Dict[int, int] = {}

async def render_screen(
    client: Client,
    target: Union[CallbackQuery, Message, int],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: ParseMode = ParseMode.HTML,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """
    Renderiza una pantalla editando SIEMPRE el mismo y único mensaje activo del bot.
    Elimina la duplicación de mensajes en el chat para mantener la interfaz limpia de 1 solo mensaje.
    """
    user_id: Optional[int] = None
    msg_to_edit_id: Optional[int] = None

    if isinstance(target, CallbackQuery):
        user_id = target.from_user.id
        if target.message:
            msg_to_edit_id = target.message.id
    elif isinstance(target, Message):
        user_id = target.chat.id
        msg_to_edit_id = USER_LAST_MESSAGES.get(user_id) or target.id
    elif isinstance(target, int):
        user_id = target
        msg_to_edit_id = USER_LAST_MESSAGES.get(user_id)

    if not user_id:
        return None

    # 1. Intentar editar el mensaje existente si tenemos su ID
    if msg_to_edit_id:
        try:
            edited_msg = await client.edit_message_text(
                chat_id=user_id,
                message_id=msg_to_edit_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            USER_LAST_MESSAGES[user_id] = msg_to_edit_id
            if isinstance(target, CallbackQuery):
                try:
                    await target.answer()
                except Exception:
                    pass
            return edited_msg
        except MessageNotModified:
            if isinstance(target, CallbackQuery):
                try:
                    await target.answer()
                except Exception:
                    pass
            return None
        except (BadRequest, MessageIdInvalid):
            # Si no se puede editar (ej: mensaje borrado por el usuario o mensaje de bienvenida inicial), procedemos a enviar uno nuevo
            pass

    # 2. Si no se pudo editar o no había mensaje anterior, enviamos el mensaje y guardamos su ID
    try:
        new_msg = await client.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        USER_LAST_MESSAGES[user_id] = new_msg.id
        if isinstance(target, CallbackQuery):
            try:
                await target.answer()
            except Exception:
                pass
        return new_msg
    except Exception as e:
        print(f"[render_screen send Error]: {e}")
        return None
