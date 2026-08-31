from typing import Optional, Union
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, BadRequest

async def render_screen(
    client: Client,
    target: Union[CallbackQuery, Message, int],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: ParseMode = ParseMode.HTML,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """
    Renderiza una pantalla editando siempre el mensaje existente.
    Si no se puede editar (ej: mensaje borrado o muy antiguo), envía un mensaje nuevo.
    """
    try:
        if isinstance(target, CallbackQuery):
            if target.message:
                try:
                    return await target.message.edit_text(
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
                except MessageNotModified:
                    # El contenido es exactamente igual, ignorar error
                    await target.answer()
                    return target.message
                except BadRequest:
                    return await client.send_message(
                        chat_id=target.from_user.id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview
                    )
            else:
                return await client.send_message(
                    chat_id=target.from_user.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )

        elif isinstance(target, Message):
            try:
                return await target.edit_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
            except MessageNotModified:
                return target
            except BadRequest:
                return await client.send_message(
                    chat_id=target.chat.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )

        elif isinstance(target, int):
            # Target es chat_id
            return await client.send_message(
                chat_id=target,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )

    except Exception as e:
        print(f"[render_screen Error]: {e}")
        return None
