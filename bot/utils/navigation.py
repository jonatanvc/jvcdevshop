from typing import Optional, Union, Dict
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, BadRequest, MessageIdInvalid
from bot.utils.emojis import parse_emojis, parse_keyboard, strip_keyboard_icons

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
    Si el mensaje anterior contenía una foto/media (como el código QR), lo elimina primero
    para evitar que queden imágenes huérfanas en el chat.
    """
    user_id: Optional[int] = None
    msg_to_edit_id: Optional[int] = None
    is_media_msg = False

    if isinstance(target, CallbackQuery):
        user_id = target.from_user.id
        if target.message:
            msg_to_edit_id = target.message.id
            if target.message.photo or target.message.video or target.message.document:
                is_media_msg = True
    elif isinstance(target, Message):
        user_id = target.chat.id
        msg_to_edit_id = USER_LAST_MESSAGES.get(user_id) or target.id
        if target.photo or target.video or target.document:
            is_media_msg = True
    elif isinstance(target, int):
        user_id = target
        msg_to_edit_id = USER_LAST_MESSAGES.get(user_id)

    if not user_id:
        return None

    if text:
        text = parse_emojis(text)

    if reply_markup:
        reply_markup = parse_keyboard(reply_markup)

    # Si el mensaje actual es una foto/media, no se puede editar a solo texto con edit_message_text
    # En este caso borramos el mensaje de foto anterior y creamos uno nuevo limpio
    if is_media_msg and isinstance(target, CallbackQuery) and target.message:
        try:
            await target.message.delete()
        except Exception:
            pass
        msg_to_edit_id = None

    # 1. Intentar editar el mensaje de texto existente si tenemos su ID
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
        except (BadRequest, MessageIdInvalid) as e:
            USER_LAST_MESSAGES.pop(user_id, None)
            if reply_markup and ("BUTTON" in str(e).upper() or "CONSTRUCTOR" in str(e).upper()):
                try:
                    clean_kb = strip_keyboard_icons(reply_markup)
                    edited_msg = await client.edit_message_text(
                        chat_id=user_id,
                        message_id=msg_to_edit_id,
                        text=text,
                        reply_markup=clean_kb,
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
                except Exception:
                    pass
        except Exception:
            USER_LAST_MESSAGES.pop(user_id, None)

    # 2. Si no se pudo editar o era una foto previa, enviamos el mensaje y guardamos su ID
    try:
        new_msg = await client.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        USER_LAST_MESSAGES[user_id] = new_msg.id

        if len(USER_LAST_MESSAGES) > 5000:
            keys_to_remove = list(USER_LAST_MESSAGES.keys())[:-2000]
            for k in keys_to_remove:
                USER_LAST_MESSAGES.pop(k, None)
        if isinstance(target, CallbackQuery):
            try:
                await target.answer()
            except Exception:
                pass
        return new_msg
    except Exception as e:
        if reply_markup:
            try:
                clean_kb = strip_keyboard_icons(reply_markup)
                new_msg = await client.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=clean_kb,
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
            except Exception as e2:
                print(f"[render_screen fallback Error]: {e2}")
        print(f"[render_screen send Error]: {e}")
        return None
