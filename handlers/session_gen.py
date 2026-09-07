"""
handlers/session_gen.py
Logic inti untuk generate session string secara interaktif, baik untuk
Telethon maupun Pyrogram. Dijalankan sebagai asyncio.Task terpisah per
user (lihat handlers/callbacks.py) sehingga bersifat non-blocking.
"""

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    FloodWaitError,
)

from config import SESSION_API_ID, SESSION_API_HASH, CONVERSATION_TIMEOUT
from utils.keyboards import cancel_kb, back_to_menu_kb

CANCEL_WORDS = {"/cancel", "batal", "cancel"}


async def run_generate_session(bot, event, library: str):
    """Entry point. Dipanggil lewat asyncio.create_task."""
    chat_id = event.chat_id
    try:
        if library == "telethon":
            await _generate_telethon(bot, chat_id)
        elif library == "pyrogram":
            await _generate_pyrogram(bot, chat_id)
        else:
            await bot.send_message(chat_id, "❌ Library tidak dikenali.")
    except asyncio.CancelledError:
        await bot.send_message(chat_id, "🛑 Proses dibatalkan.")
        raise
    except asyncio.TimeoutError:
        await bot.send_message(
            chat_id,
            "⏰ Waktu habis, kamu tidak merespon. Silakan ulangi dari menu.",
            buttons=back_to_menu_kb(),
        )
    except Exception as e:
        await bot.send_message(
            chat_id,
            f"❌ Terjadi kesalahan tak terduga:\n`{type(e).__name__}: {e}`",
            buttons=back_to_menu_kb(),
        )


async def _ask(bot, conv, text, buttons=None):
    # PENTING: harus lewat conv.send_message() (bukan bot.send_message()
    # langsung), karena conv.get_response() menunggu balasan atas pesan
    # TERAKHIR yang dikirim melalui objek `conv` itu sendiri. Kalau kita
    # kirim lewat bot.send_message() biasa, Telethon tidak tahu pesan mana
    # yang harus ditunggu balasannya dan melempar
    # `ValueError: No message was sent previously`.
    await conv.send_message(text, buttons=buttons or cancel_kb())
    resp = await conv.get_response(timeout=CONVERSATION_TIMEOUT)
    if resp.raw_text.strip().lower() in CANCEL_WORDS:
        raise asyncio.CancelledError()
    return resp.raw_text.strip()


# ----------------------------------------------------------------------
# TELETHON FLOW
# ----------------------------------------------------------------------
async def _generate_telethon(bot, chat_id):
    async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
        phone = await _ask(
            bot, conv,
            "📱 **Kirim nomor telepon** akun Telegram kamu.\n"
            "Format: `+62812xxxxxxx` (pakai kode negara)\n\n"
            "Ketik /cancel untuk membatalkan.",
        )

        client = TelegramClient(StringSession(), SESSION_API_ID, SESSION_API_HASH)
        await client.connect()

        try:
            sent = await client.send_code_request(phone)
        except PhoneNumberInvalidError:
            await bot.send_message(chat_id, "❌ Nomor telepon tidak valid. Silakan ulangi dari menu.")
            await client.disconnect()
            return
        except FloodWaitError as e:
            await bot.send_message(chat_id, f"⏳ Kena flood wait, coba lagi setelah {e.seconds} detik.")
            await client.disconnect()
            return

        code = await _ask(
            bot, conv,
            "🔢 **Masukkan kode OTP** yang dikirim ke akun Telegram kamu.\n"
            "_Tips: pisahkan dengan spasi contoh `1 2 3 4 5` jika Telegram "
            "memblokir pengiriman kode utuh._",
        )
        code = code.replace(" ", "")

        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except PhoneCodeInvalidError:
            await bot.send_message(chat_id, "❌ Kode OTP salah. Silakan ulangi dari menu.")
            await client.disconnect()
            return
        except PhoneCodeExpiredError:
            await bot.send_message(chat_id, "❌ Kode OTP kedaluwarsa. Silakan ulangi dari menu.")
            await client.disconnect()
            return
        except SessionPasswordNeededError:
            for attempt in range(3):
                password = await _ask(
                    bot, conv,
                    "🔐 Akun kamu memakai **verifikasi 2 langkah**.\n"
                    "Masukkan password kamu:",
                )
                try:
                    await client.sign_in(password=password)
                    break
                except PasswordHashInvalidError:
                    if attempt == 2:
                        await bot.send_message(chat_id, "❌ Password salah 3x. Silakan ulangi dari menu.")
                        await client.disconnect()
                        return
                    await bot.send_message(chat_id, "❌ Password salah, coba lagi.")

        session_string = client.session.save()
        await client.disconnect()

        await bot.send_message(
            chat_id,
            "✅ **Session Telethon berhasil dibuat!**\n\n"
            f"```\n{session_string}\n```\n\n"
            "⚠️ **JANGAN bagikan session string ini ke siapa pun.**\n"
            "Segera hapus pesan ini setelah kamu menyimpannya.",
            buttons=back_to_menu_kb(),
        )


# ----------------------------------------------------------------------
# PYROGRAM FLOW
# ----------------------------------------------------------------------
async def _generate_pyrogram(bot, chat_id):
    from pyrogram import Client
    from pyrogram.errors import (
        PhoneNumberInvalid,
        PhoneCodeInvalid,
        PhoneCodeExpired,
        SessionPasswordNeeded,
        PasswordHashInvalid,
        FloodWait,
    )

    async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
        phone = await _ask(
            bot, conv,
            "📱 **Kirim nomor telepon** akun Telegram kamu.\n"
            "Format: `+62812xxxxxxx` (pakai kode negara)\n\n"
            "Ketik /cancel untuk membatalkan.",
        )

        client = Client(
            name=":memory:",
            api_id=SESSION_API_ID,
            api_hash=SESSION_API_HASH,
            in_memory=True,
        )
        await client.connect()

        try:
            sent = await client.send_code(phone)
        except PhoneNumberInvalid:
            await bot.send_message(chat_id, "❌ Nomor telepon tidak valid. Silakan ulangi dari menu.")
            await client.disconnect()
            return
        except FloodWait as e:
            await bot.send_message(chat_id, f"⏳ Kena flood wait, coba lagi setelah {e.value} detik.")
            await client.disconnect()
            return

        code = await _ask(
            bot, conv,
            "🔢 **Masukkan kode OTP** yang dikirim ke akun Telegram kamu.\n"
            "_Tips: pisahkan dengan spasi contoh `1 2 3 4 5` jika Telegram "
            "memblokir pengiriman kode utuh._",
        )
        code = code.replace(" ", "")

        try:
            await client.sign_in(phone, sent.phone_code_hash, code)
        except PhoneCodeInvalid:
            await bot.send_message(chat_id, "❌ Kode OTP salah. Silakan ulangi dari menu.")
            await client.disconnect()
            return
        except PhoneCodeExpired:
            await bot.send_message(chat_id, "❌ Kode OTP kedaluwarsa. Silakan ulangi dari menu.")
            await client.disconnect()
            return
        except SessionPasswordNeeded:
            for attempt in range(3):
                password = await _ask(
                    bot, conv,
                    "🔐 Akun kamu memakai **verifikasi 2 langkah**.\n"
                    "Masukkan password kamu:",
                )
                try:
                    await client.check_password(password)
                    break
                except PasswordHashInvalid:
                    if attempt == 2:
                        await bot.send_message(chat_id, "❌ Password salah 3x. Silakan ulangi dari menu.")
                        await client.disconnect()
                        return
                    await bot.send_message(chat_id, "❌ Password salah, coba lagi.")

        session_string = await client.export_session_string()
        await client.disconnect()

        await bot.send_message(
            chat_id,
            "✅ **Session Pyrogram berhasil dibuat!**\n\n"
            f"```\n{session_string}\n```\n\n"
            "⚠️ **JANGAN bagikan session string ini ke siapa pun.**\n"
            "Segera hapus pesan ini setelah kamu menyimpannya.",
            buttons=back_to_menu_kb(),
        )
