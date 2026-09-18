import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, update
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import User, SupportTicket, TicketMessage
from bot.utils.navigation import render_screen
from bot.utils.rate_limit import rate_limiter
from bot.utils.emojis import parse_emojis, parse_keyboard

# Estados en memoria para captura de mensajes de soporte
SUPPORT_USER_STATES: Dict[int, Dict[str, Any]] = {}
ADMIN_TICKET_STATES: Dict[int, Dict[str, Any]] = {}

def is_admin(user_id: int) -> bool:
    return settings.is_owner(user_id) or (bool(settings.admin_ids) and user_id in settings.admin_ids)

def register_support_handlers(app: Client):

    # ========================================================
    # 🆘 1. MENÚ PRINCIPAL DE SOPORTE
    # ========================================================

    @app.on_message(filters.command(["soporte", "support", "ayuda", "help"]) & filters.private)
    async def cmd_support(client: Client, message: Message):
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception:
            pass
        if rate_limiter.is_rate_limited(user_id):
            return
        SUPPORT_USER_STATES.pop(user_id, None)
        await show_support_menu(client, user_id, user_id)

    @app.on_callback_query(filters.regex(r"^support:(view|menu)$"))
    async def cb_support_menu(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return
        SUPPORT_USER_STATES.pop(user_id, None)
        await show_support_menu(client, callback, user_id)

    async def show_support_menu(client: Client, target: Any, user_id: int):
        async with async_session() as session:
            user_res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user_res.scalar_one_or_none()
            lang = getattr(user, "language", "es") or "es"

            # Contar tickets abiertos del usuario
            open_count_stmt = select(func.count(SupportTicket.id)).where(
                SupportTicket.user_id == user_id,
                SupportTicket.status == "OPEN"
            )
            open_res = await session.execute(open_count_stmt)
            open_tickets = open_res.scalar() or 0

            # Contar total de tickets
            total_stmt = select(func.count(SupportTicket.id)).where(SupportTicket.user_id == user_id)
            total_res = await session.execute(total_stmt)
            total_tickets = total_res.scalar() or 0

        status_note = f"\n🟢 <i>Tienes <b>{open_tickets}</b> ticket(s) en curso con nuestro equipo.</i>\n" if open_tickets > 0 else ""

        text = (
            f"🆘 <b>CENTRO DE ATENCIÓN Y SOPORTE</b>\n\n"
            f"¿Tienes alguna duda con una compra, necesitas asistencia técnica o quieres consultar un servicio?\n"
            f"{status_note}\n"
            f"• <b>Tiempo promedio de respuesta:</b> <code>&lt; 15 minutos</code>\n"
            f"• <b>Horario de atención:</b> <code>24/7 Soporte Automatizado &amp; Staff</code>\n\n"
            f"<i>Puedes abrir un ticket interactivo dentro del bot (con capturas de pantalla) para recibir asistencia de nuestro equipo:</i>"
        )
        if lang == "en":
            text = (
                f"🆘 <b>CUSTOMER SUPPORT CENTER</b>\n\n"
                f"Do you have any questions about a purchase, need technical assistance, or want to inquire about a service?\n"
                f"{status_note}\n"
                f"• <b>Average response time:</b> <code>&lt; 15 minutes</code>\n"
                f"• <b>Availability:</b> <code>24/7 Automated &amp; Staff Support</code>\n\n"
                f"<i>You can open a support ticket directly inside the bot (including screenshots) to get assistance from our team:</i>"
            )
        elif lang == "pt":
            text = (
                f"🆘 <b>CENTRO DE ATENDIMENTO E SUPORTE</b>\n\n"
                f"Tem alguma dúvida sobre uma compra, precisa de suporte técnico ou quer saber mais sobre um serviço?\n"
                f"{status_note}\n"
                f"• <b>Tempo médio de resposta:</b> <code>&lt; 15 minutos</code>\n"
                f"• <b>Horário:</b> <code>24/7 Suporte Automatizado e Staff</code>\n\n"
                f"<i>Abra um ticket interativo aqui no bot (com capturas de tela) para receber assistência da nossa equipe:</i>"
            )

        btn_new = "💬 Abrir Nuevo Ticket" if lang == "es" else ("💬 Open New Ticket" if lang == "en" else "💬 Abrir Novo Ticket")
        btn_list = f"📋 Mis Tickets ({total_tickets})" if lang == "es" else (f"📋 My Tickets ({total_tickets})" if lang == "en" else f"📋 Meus Tickets ({total_tickets})")
        btn_back = "🔙 Volver al Menú" if lang == "es" else ("🔙 Back to Menu" if lang == "en" else "🔙 Voltar ao Menu")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_new, callback_data="support:new")],
            [InlineKeyboardButton(btn_list, callback_data="support:list:1")],
            [InlineKeyboardButton(btn_back, callback_data="menu_main")]
        ])

        await render_screen(client, target, text, keyboard)

    # ========================================================
    # 📝 2. CREACIÓN DE NUEVO TICKET
    # ========================================================

    @app.on_callback_query(filters.regex(r"^support:new$"))
    async def cb_support_new(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        SUPPORT_USER_STATES[user_id] = {"action": "waiting_ticket_content"}

        text = (
            f"✍️ <b>NUEVO TICKET DE SOPORTE</b>\n\n"
            f"Por favor describe detalladamente tu consulta, inconveniente o duda.\n\n"
            f"📸 <i>También puedes enviar una <b>foto o captura de pantalla</b> con subtítulo.</i>\n\n"
            f"<i>Pulsa Cancelar si deseas regresar.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="support:view")]
        ])
        await render_screen(client, callback, text, keyboard)

    # ========================================================
    # 📋 3. LISTADO DE TICKETS DEL USUARIO
    # ========================================================

    @app.on_callback_query(filters.regex(r"^support:list:(\d+)$"))
    async def cb_support_list(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        page = int(callback.matches[0].group(1))
        page_size = 4

        async with async_session() as session:
            count_stmt = select(func.count(SupportTicket.id)).where(SupportTicket.user_id == user_id)
            count_res = await session.execute(count_stmt)
            total_tickets = count_res.scalar() or 0

            if total_tickets == 0:
                empty_text = (
                    f"📋 <b>HISTORIAL DE TICKETS</b>\n\n"
                    f"Aún no has creado ningún ticket de soporte.\n\n"
                    f"<i>Si tienes dudas o necesitas asistencia con un pedido, pulsa el botón a continuación para abrir uno.</i>"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Abrir Nuevo Ticket", callback_data="support:new")],
                    [InlineKeyboardButton("🔙 Volver a Soporte", callback_data="support:view")]
                ])
                await render_screen(client, callback, empty_text, keyboard)
                return

            total_pages = max(1, (total_tickets + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            tickets_stmt = (
                select(SupportTicket)
                .where(SupportTicket.user_id == user_id)
                .order_by(SupportTicket.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            tickets_res = await session.execute(tickets_stmt)
            tickets = tickets_res.scalars().all()

        text = (
            f"📋 <b>TUS TICKETS DE SOPORTE ({total_tickets})</b>\n\n"
            f"Página: <code>{page}/{total_pages}</code>\n\n"
            f"<i>Selecciona un ticket para ver la conversación y responder:</i>"
        )

        buttons = []
        for tk in tickets:
            status_emoji = "🟢 Abierto" if tk.status == "OPEN" else ("✅ Resuelto" if tk.status == "RESOLVED" else "🔒 Cerrado")
            created_str = tk.created_at.strftime("%d/%m %H:%M") if tk.created_at else ""
            subj_preview = (tk.subject or "Consulta")[0:25]
            btn_lbl = f"#{tk.id} • {subj_preview} ({status_emoji}) [{created_str}]"
            buttons.append([InlineKeyboardButton(btn_lbl, callback_data=f"support:ticket:view:{tk.id}")])

        if total_pages > 1:
            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton("◀️", callback_data=f"support:list:{page - 1}"))
            else:
                nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))
            nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                nav_row.append(InlineKeyboardButton("▶️", callback_data=f"support:list:{page + 1}"))
            else:
                nav_row.append(InlineKeyboardButton("🔵", callback_data="noop"))
            buttons.append(nav_row)

        buttons.append([
            InlineKeyboardButton("💬 Abrir Nuevo Ticket", callback_data="support:new"),
            InlineKeyboardButton("🔙 Volver a Soporte", callback_data="support:view")
        ])

        await render_screen(client, callback, text, InlineKeyboardMarkup(buttons))

    # ========================================================
    # 🔍 4. DETALLE DE UN TICKET Y CONVERSACIÓN
    # ========================================================

    @app.on_callback_query(filters.regex(r"^support:ticket:view:(\d+)$"))
    async def cb_support_ticket_view(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        ticket_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id)
            res = await session.execute(stmt)
            ticket = res.scalar_one_or_none()

            if not ticket:
                await callback.answer("❌ Ticket no encontrado.", show_alert=True)
                return

            # Cargar los mensajes del ticket (últimos 10)
            msg_stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at.asc())
            msg_res = await session.execute(msg_stmt)
            messages = msg_res.scalars().all()

        status_tag = "🟢 ABIERTO (Esperando respuesta)" if ticket.status == "OPEN" else ("✅ RESUELTO" if ticket.status == "RESOLVED" else "🔒 CERRADO")
        date_created = ticket.created_at.strftime("%Y-%m-%d %H:%M") if ticket.created_at else "N/A"

        header = (
            f"🎫 <b>TICKET DE SOPORTE #{ticket.id}</b>\n\n"
            f"• <b>Estado:</b> <code>{status_tag}</code>\n"
            f"• <b>Fecha:</b> <code>{date_created}</code>\n"
            f"• <b>Asunto:</b> <i>{ticket.subject or 'Consulta general'}</i>\n\n"
            f"💬 <b>HISTORIAL DE MENSAJES:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        msg_lines = []
        for m in messages[-8:]:
            author = "👨‍💻 <b>Soporte Oficial:</b>" if m.is_admin else "👤 <b>Tú:</b>"
            time_str = m.created_at.strftime("%H:%M") if m.created_at else ""
            m_text = m.message_text or "[📸 Foto adjunta]"
            msg_lines.append(f"{author} (<i>{time_str}</i>)\n{m_text}")

        conversation_body = "\n\n".join(msg_lines) if msg_lines else "<i>Sin mensajes registrados.</i>"
        full_text = header + conversation_body

        keyboard_buttons = []
        if ticket.status == "OPEN":
            keyboard_buttons.append([
                InlineKeyboardButton("✍️ Responder / Agregar Mensaje", callback_data=f"support:ticket:reply:{ticket.id}"),
                InlineKeyboardButton("✅ Marcar como Resuelto", callback_data=f"support:ticket:close:{ticket.id}")
            ])
        else:
            keyboard_buttons.append([
                InlineKeyboardButton("🔄 Reabrir Ticket", callback_data=f"support:ticket:reply:{ticket.id}")
            ])

        keyboard_buttons.append([
            InlineKeyboardButton("🔙 Mis Tickets", callback_data="support:list:1"),
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")
        ])

        await render_screen(client, callback, full_text, InlineKeyboardMarkup(keyboard_buttons))

    # ========================================================
    # ✍️ 5. RESPUESTA DEL USUARIO A UN TICKET
    # ========================================================

    @app.on_callback_query(filters.regex(r"^support:ticket:reply:(\d+)$"))
    async def cb_support_ticket_reply(client: Client, callback: CallbackQuery):
        try:
            await callback.answer()
        except Exception:
            pass
        user_id = callback.from_user.id
        if rate_limiter.is_rate_limited(user_id):
            return

        ticket_id = int(callback.matches[0].group(1))
        SUPPORT_USER_STATES[user_id] = {
            "action": "waiting_ticket_reply",
            "ticket_id": ticket_id
        }

        text = (
            f"✍️ <b>RESPONDER AL TICKET #{ticket_id}</b>\n\n"
            f"Envía a continuación tu mensaje o consulta de seguimiento.\n\n"
            f"📸 <i>También puedes adjuntar una foto o comprobante.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data=f"support:ticket:view:{ticket_id}")]
        ])
        await render_screen(client, callback, text, keyboard)

    @app.on_callback_query(filters.regex(r"^support:ticket:close:(\d+)$"))
    async def cb_support_ticket_close(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        ticket_id = int(callback.matches[0].group(1))

        async with async_session() as session:
            stmt = select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id)
            res = await session.execute(stmt)
            ticket = res.scalar_one_or_none()
            if ticket:
                ticket.status = "RESOLVED"
                await session.commit()

        await callback.answer("✅ Ticket marcado como resuelto. ¡Gracias!", show_alert=True)
        await cb_support_ticket_view(client, callback)

    # ========================================================
    # 👨‍💻 6. RESPUESTA Y GESTIÓN DEL ADMINISTRADOR
    # ========================================================

    @app.on_callback_query(filters.regex(r"^admin:ticket:reply:(\d+)$"))
    async def cb_admin_ticket_reply(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            await callback.answer("⛔ No autorizado.", show_alert=True)
            return

        ticket_id = int(callback.matches[0].group(1))
        ADMIN_TICKET_STATES[user_id] = {
            "action": "waiting_admin_reply",
            "ticket_id": ticket_id
        }

        await callback.answer()
        await callback.message.reply_text(
            f"✍️ <b>Escribe tu respuesta para el Ticket #{ticket_id}:</b>\n\n"
            f"<i>Envía el texto o foto que se le entregará directamente al cliente.</i>\n"
            f"<i>O usa el comando: <code>/reply {ticket_id} tu mensaje</code></i>"
        )

    @app.on_callback_query(filters.regex(r"^admin:ticket:close:(\d+)$"))
    async def cb_admin_ticket_close(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not is_admin(user_id):
            return

        ticket_id = int(callback.matches[0].group(1))
        async with async_session() as session:
            stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
            res = await session.execute(stmt)
            ticket = res.scalar_one_or_none()
            if ticket:
                ticket.status = "CLOSED"
                target_uid = ticket.user_id
                await session.commit()
            else:
                target_uid = None

        await callback.answer(f"Ticket #{ticket_id} cerrado.", show_alert=True)
        try:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n🔒 <b>[TICKET CERRADO POR ADMIN]</b>"
            )
        except Exception:
            pass

        if target_uid:
            try:
                await client.send_message(
                    chat_id=target_uid,
                    text=parse_emojis(f"🔒 <b>Tu Ticket #{ticket_id} ha sido cerrado por el equipo de soporte.</b>\n\n<i>Si requieres más ayuda, puedes abrir uno nuevo en cualquier momento.</i>"),
                    reply_markup=parse_keyboard(InlineKeyboardMarkup([[InlineKeyboardButton("📋 Mis Tickets", callback_data="support:list:1")]])),
                    disable_web_page_preview=True
                )
            except Exception:
                pass

    @app.on_message(filters.command("reply") & filters.private)
    async def cmd_admin_reply(client: Client, message: Message):
        user_id = message.from_user.id
        if not is_admin(user_id):
            return

        try:
            await message.delete()
        except Exception:
            pass

        if len(message.command) < 3:
            await client.send_message(
                chat_id=user_id,
                text="⚠️ <b>Uso correcto:</b> <code>/reply &lt;ticket_id&gt; &lt;tu respuesta&gt;</code>\nEjemplo: <code>/reply 12 Hola, ya revisamos tu caso y tu cuenta está activa.</code>"
            )
            return

        ticket_arg = message.command[1].replace("#", "").replace("T-", "").replace("T", "").strip()
        if not ticket_arg.isdigit():
            await client.send_message(chat_id=user_id, text="❌ El ID del ticket debe ser numérico.")
            return

        ticket_id = int(ticket_arg)
        reply_text = " ".join(message.command[2:]).strip()

        await deliver_admin_ticket_reply(client, user_id, ticket_id, reply_text)

    # ========================================================
    # 📨 7. CAPTURADOR GLOBAL DE MENSAJES PARA TICKETS
    # ========================================================

    @app.on_message(filters.private & ~filters.command(["start", "admin", "buscar", "search", "catalogo", "catalog", "pedidos", "orders", "depositar", "deposit", "saldo", "wallet", "soporte", "support", "ayuda", "help", "del", "dep", "user", "reply", "vip"]), group=4)
    async def handle_ticket_message(client: Client, message: Message):
        user_id = message.from_user.id

        # 1. ¿Es una respuesta de un Administrador?
        if is_admin(user_id) and user_id in ADMIN_TICKET_STATES:
            state = ADMIN_TICKET_STATES.pop(user_id)
            if state.get("action") == "waiting_admin_reply":
                ticket_id = state.get("ticket_id")
                reply_text = message.text or message.caption or ""
                await deliver_admin_ticket_reply(client, user_id, ticket_id, reply_text)
                return

        # 2. ¿Es un usuario creando o respondiendo un ticket?
        user_state = SUPPORT_USER_STATES.get(user_id)
        if not user_state:
            message.continue_propagation()
            return

        action = user_state.get("action")
        try:
            await message.delete()
        except Exception:
            pass

        # Determinar contenido y multimedia
        content_text = message.text or message.caption or ""
        media_id = None
        media_type = None

        if message.photo:
            media_id = message.photo.file_id
            media_type = "photo"
        elif message.document:
            media_id = message.document.file_id
            media_type = "document"

        if not content_text and not media_id:
            await client.send_message(chat_id=user_id, text="⚠️ Por favor escribe un mensaje o adjunta una imagen.")
            return

        if action == "waiting_ticket_content":
            SUPPORT_USER_STATES.pop(user_id, None)

            subject_str = content_text[:60] if content_text else "Adjunto de usuario"

            async with async_session() as session:
                new_ticket = SupportTicket(
                    user_id=user_id,
                    status="OPEN",
                    subject=subject_str
                )
                session.add(new_ticket)
                await session.commit()
                await session.refresh(new_ticket)

                t_msg = TicketMessage(
                    ticket_id=new_ticket.id,
                    sender_id=user_id,
                    is_admin=False,
                    message_text=content_text,
                    media_file_id=media_id,
                    media_type=media_type
                )
                session.add(t_msg)
                await session.commit()

                ticket_id = new_ticket.id

            # Confirmar al cliente
            conf_text = (
                f"✅ <b>¡TICKET CREADO EXITOSAMENTE!</b>\n\n"
                f"• <b>Número de Ticket:</b> <code>#T-{ticket_id}</code>\n"
                f"• <b>Estado:</b> <code>🟢 ABIERTO</code>\n\n"
                f"<i>Tu consulta fue remitida a nuestro equipo de soporte. Te responderemos directamente por aquí a la brevedad posible.</i>"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🔍 Ver Ticket #{ticket_id}", callback_data=f"support:ticket:view:{ticket_id}")],
                [InlineKeyboardButton("📋 Mis Tickets", callback_data="support:list:1")],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(client, user_id, conf_text, keyboard)

            # Notificar al grupo de auditoría / canal admin
            await notify_admins_new_ticket(client, ticket_id, user_id, message.from_user.username, content_text, media_id, media_type)
            return

        elif action == "waiting_ticket_reply":
            SUPPORT_USER_STATES.pop(user_id, None)
            ticket_id = user_state.get("ticket_id")

            async with async_session() as session:
                t_stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
                t_res = await session.execute(t_stmt)
                ticket = t_res.scalar_one_or_none()

                if not ticket:
                    await client.send_message(chat_id=user_id, text="❌ El ticket no existe.")
                    return

                ticket.status = "OPEN"
                ticket.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                t_msg = TicketMessage(
                    ticket_id=ticket_id,
                    sender_id=user_id,
                    is_admin=False,
                    message_text=content_text,
                    media_file_id=media_id,
                    media_type=media_type
                )
                session.add(t_msg)
                await session.commit()

            conf_text = (
                f"✅ <b>RESPUESTA ENVIADA AL TICKET #{ticket_id}</b>\n\n"
                f"Tu mensaje ha sido agregado al historial del caso."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Ver Conversación", callback_data=f"support:ticket:view:{ticket_id}")],
                [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_main")]
            ])
            await render_screen(client, user_id, conf_text, keyboard)

            # Notificar al staff
            await notify_admins_ticket_update(client, ticket_id, user_id, message.from_user.username, content_text, media_id, media_type)
            return

        message.continue_propagation()

async def deliver_admin_ticket_reply(client: Client, admin_id: int, ticket_id: int, reply_text: str):
    """Guarda la respuesta del admin y la entrega al usuario por DM"""
    if not reply_text.strip():
        await client.send_message(chat_id=admin_id, text="❌ El mensaje de respuesta no puede estar vacío.")
        return

    async with async_session() as session:
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        res = await session.execute(stmt)
        ticket = res.scalar_one_or_none()

        if not ticket:
            await client.send_message(chat_id=admin_id, text=f"❌ Ticket #{ticket_id} no encontrado.")
            return

        target_uid = ticket.user_id
        ticket.status = "RESOLVED"
        ticket.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        msg = TicketMessage(
            ticket_id=ticket_id,
            sender_id=admin_id,
            is_admin=True,
            message_text=reply_text
        )
        session.add(msg)
        await session.commit()

    # Confirmación al Admin
    await client.send_message(
        chat_id=admin_id,
        text=parse_emojis(f"✅ <b>Respuesta entregada al cliente del Ticket #{ticket_id}.</b>")
    )

    # Envío al Cliente por DM
    dm_text = (
        f"💬 <b>RESPUESTA DE SOPORTE (Ticket #{ticket_id})</b>\n\n"
        f"👨‍💻 <b>Atención al Cliente:</b>\n"
        f"«<i>{reply_text}</i>»\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Si tu duda fue aclarada, puedes marcar el ticket como resuelto. Si requieres más ayuda, pulsa responder:</i>"
    )
    dm_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✍️ Responder", callback_data=f"support:ticket:reply:{ticket_id}"),
            InlineKeyboardButton("✅ Marcar Resuelto", callback_data=f"support:ticket:close:{ticket_id}")
        ],
        [
            InlineKeyboardButton("🔍 Ver Todo el Ticket", callback_data=f"support:ticket:view:{ticket_id}")
        ]
    ])
    try:
        await client.send_message(chat_id=target_uid, text=parse_emojis(dm_text), reply_markup=parse_keyboard(dm_keyboard))
    except Exception as e:
        print(f"[DeliverReply Error]: {e}")

async def notify_admins_new_ticket(client: Client, ticket_id: int, user_id: int, username: Optional[str], content_text: str, media_id: Optional[str], media_type: Optional[str]):
    """Envía notificación de nuevo ticket al canal/grupo de administración"""
    user_tag = f"@{username}" if username else f"ID: <code>{user_id}</code>"
    preview = content_text if content_text else "[📸 Foto/Comprobante adjunto]"

    admin_text = (
        f"🆘 <b>NUEVO TICKET DE SOPORTE #T-{ticket_id}</b>\n\n"
        f"👤 <b>Usuario:</b> {user_tag} (<code>{user_id}</code>)\n"
        f"📝 <b>Mensaje:</b>\n{preview}\n\n"
        f"<i>Puedes responder con el botón de abajo o escribiendo:</i>\n"
        f"<code>/reply {ticket_id} tu respuesta</code>"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✍️ Responder Ticket", callback_data=f"admin:ticket:reply:{ticket_id}"),
            InlineKeyboardButton("✅ Marcar Resuelto", callback_data=f"admin:ticket:close:{ticket_id}")
        ],
        [
            InlineKeyboardButton("👤 Ficha de Usuario", callback_data=f"admin:user_card:{user_id}")
        ]
    ])

    target_chat = settings.LOG_GROUP_ID if settings.LOG_GROUP_ID != 0 else (settings.admin_ids[0] if settings.admin_ids else 8670239783)

    try:
        if media_id and media_type == "photo":
            await client.send_photo(chat_id=target_chat, photo=media_id, caption=parse_emojis(admin_text), reply_markup=parse_keyboard(keyboard))
        else:
            await client.send_message(chat_id=target_chat, text=parse_emojis(admin_text), reply_markup=parse_keyboard(keyboard))
    except Exception as e:
        print(f"[NotifyNewTicket Error]: {e}")

async def notify_admins_ticket_update(client: Client, ticket_id: int, user_id: int, username: Optional[str], content_text: str, media_id: Optional[str], media_type: Optional[str]):
    """Envía notificación al staff cuando el usuario añade un mensaje a su ticket"""
    user_tag = f"@{username}" if username else f"ID: <code>{user_id}</code>"
    admin_text = (
        f"🔔 <b>ACTUALIZACIÓN EN TICKET #T-{ticket_id}</b>\n\n"
        f"👤 <b>Usuario:</b> {user_tag}\n"
        f"💬 <b>Nuevo Mensaje:</b>\n{content_text or '[📸 Foto/Adjunto]'}\n\n"
        f"<code>/reply {ticket_id} tu respuesta</code>"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✍️ Responder", callback_data=f"admin:ticket:reply:{ticket_id}"),
            InlineKeyboardButton("✅ Cerrar Ticket", callback_data=f"admin:ticket:close:{ticket_id}")
        ]
    ])
    target_chat = settings.LOG_GROUP_ID if settings.LOG_GROUP_ID != 0 else (settings.admin_ids[0] if settings.admin_ids else 8670239783)
    try:
        await client.send_message(chat_id=target_chat, text=parse_emojis(admin_text), reply_markup=parse_keyboard(keyboard))
    except Exception as e:
        print(f"[NotifyTicketUpdate Error]: {e}")
