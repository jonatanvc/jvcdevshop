import asyncio
from datetime import datetime, timedelta, timezone
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from sqlalchemy import select
from bot.database.session import async_session
from bot.database.models import User
from bot.services.audit_logger import audit_logger
from bot.utils.i18n import t
from bot.utils.emojis import parse_emojis, parse_keyboard

class VIPService:
    def __init__(self):
        pass

    async def check_and_notify_expirations(self, client: Client):
        """
        Revisa periódicamente el estado de las membresías VIP para:
        1. Avisar 24h antes del vencimiento y fijar el mensaje en el chat con botón de renovación.
        2. Avisar 2h antes del vencimiento de forma urgente y fijar el mensaje en el chat con botón de renovación.
        3. Desactivar el estado VIP una vez alcanzada la fecha de expiración y notificar al usuario.
        """
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            async with async_session() as session:
                # -------------------------------------------------------------
                # 1. EXPIRADOS: is_vip == True y vip_expires_at <= now
                # -------------------------------------------------------------
                exp_stmt = select(User).where(User.is_vip == True, User.vip_expires_at <= now)
                exp_res = await session.execute(exp_stmt)
                expired_users = exp_res.scalars().all()

                for u in expired_users:
                    u.is_vip = False
                    u.vip_warned_24h = False
                    u.vip_warned_2h = False

                    lang = getattr(u, "language", "es") or "es"
                    text = t("vip_expired_msg", lang)
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton(t("btn_renew_vip", lang), callback_data="vip:confirm_screen")],
                        [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
                    ])

                    try:
                        await client.send_message(
                            chat_id=u.telegram_id,
                            text=parse_emojis(text),
                            reply_markup=parse_keyboard(kb),
                            parse_mode=ParseMode.HTML
                        )
                    except Exception:
                        pass

                    await audit_logger.log_system_alert(
                        client=client,
                        title="👑 MEMBRESÍA VIP FINALIZADA",
                        details=(
                            f"👤 <b>Usuario:</b> <code>{u.telegram_id}</code> (@{u.username or 'N/A'})\n"
                            f"<i>El período de 30 días ha concluido y regresó a cuenta Regular.</i>"
                        )
                    )

                # -------------------------------------------------------------
                # 2. AVISO 2 HORAS ANTES: is_vip == True, vip_warned_2h == False, expires_at <= now + 2h
                # -------------------------------------------------------------
                two_hours_limit = now + timedelta(hours=2)
                warn_2h_stmt = select(User).where(
                    User.is_vip == True,
                    User.vip_warned_2h == False,
                    User.vip_expires_at > now,
                    User.vip_expires_at <= two_hours_limit
                )
                warn_2h_res = await session.execute(warn_2h_stmt)
                users_2h = warn_2h_res.scalars().all()

                for u in users_2h:
                    u.vip_warned_2h = True
                    # También marcamos 24h por consistencia
                    u.vip_warned_24h = True

                    lang = getattr(u, "language", "es") or "es"
                    exp_fmt = u.vip_expires_at.strftime("%H:%M UTC (%Y-%m-%d)")
                    text = t("vip_warn_2h_msg", lang, expires_at=exp_fmt)
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton(t("btn_renew_vip", lang), callback_data="vip:confirm_screen")],
                        [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
                    ])

                    try:
                        sent_msg = await client.send_message(
                            chat_id=u.telegram_id,
                            text=parse_emojis(text),
                            reply_markup=parse_keyboard(kb),
                            parse_mode=ParseMode.HTML
                        )
                        # FIJAR MENSAJE EN EL CHAT
                        try:
                            await client.pin_chat_message(
                                chat_id=u.telegram_id,
                                message_id=sent_msg.id,
                                both_sides=True
                            )
                        except Exception:
                            # Fallback si both_sides no está soportado en privado
                            await client.pin_chat_message(
                                chat_id=u.telegram_id,
                                message_id=sent_msg.id
                            )
                    except Exception:
                        pass

                # -------------------------------------------------------------
                # 3. AVISO 24 HORAS ANTES: is_vip == True, vip_warned_24h == False, expires_at <= now + 24h
                # -------------------------------------------------------------
                twenty_four_hours_limit = now + timedelta(hours=24)
                warn_24h_stmt = select(User).where(
                    User.is_vip == True,
                    User.vip_warned_24h == False,
                    User.vip_expires_at > two_hours_limit,
                    User.vip_expires_at <= twenty_four_hours_limit
                )
                warn_24h_res = await session.execute(warn_24h_stmt)
                users_24h = warn_24h_res.scalars().all()

                for u in users_24h:
                    u.vip_warned_24h = True

                    lang = getattr(u, "language", "es") or "es"
                    exp_fmt = u.vip_expires_at.strftime("%Y-%m-%d %H:%M UTC")
                    text = t("vip_warn_24h_msg", lang, expires_at=exp_fmt)
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton(t("btn_renew_vip", lang), callback_data="vip:confirm_screen")],
                        [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_main")]
                    ])

                    try:
                        sent_msg = await client.send_message(
                            chat_id=u.telegram_id,
                            text=parse_emojis(text),
                            reply_markup=parse_keyboard(kb),
                            parse_mode=ParseMode.HTML
                        )
                        # FIJAR MENSAJE EN EL CHAT
                        try:
                            await client.pin_chat_message(
                                chat_id=u.telegram_id,
                                message_id=sent_msg.id,
                                both_sides=True
                            )
                        except Exception:
                            await client.pin_chat_message(
                                chat_id=u.telegram_id,
                                message_id=sent_msg.id
                            )
                    except Exception:
                        pass

                await session.commit()

        except Exception as e:
            print(f"[VIPService Error]: {e}")

vip_service = VIPService()
