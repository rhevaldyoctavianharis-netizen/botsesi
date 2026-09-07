"""
handlers/session_gen.py  (DIUBAH — translate nyata, aman untuk session string)
Logic inti untuk generate session string secara interaktif, baik untuk
Telethon maupun Pyrogram. Dijalankan sebagai asyncio.Task terpisah per
user (lihat handlers/callbacks.py) sehingga bersifat non-blocking.

PENTING SOAL TRANSLATE: session_string TIDAK PERNAH dilewatkan ke fungsi
translate (utils/i18n.tr_block) sama sekali. Session string itu setara
password/kredensial (base64-ish), kalau ikut "diterjemahkan" oleh Google
Translate isinya akan rusak/berubah dan bikin akun user tidak bisa login.
Semua pesan yang mengandung session_string dibuat dengan cara:
translate teks penjelasannya SAJA, lalu digabung f-string dengan
session_string APA ADANYA (lihat _send_success di bawah).
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
from utils.i18n import tr_block

CANCEL_WORDS = {"/cancel", "batal", "cancel"}


async def run_generate_session(bot, event, library: str, lang: str = "id"):
    """Entry point. Dipanggil lewat asyncio.create_task."""
    chat_id = event.chat_id
    try:
        if library == "telethon":
            await _generate_telethon(bot, chat_id, lang)
        elif library == "pyrogram":
            await _generate_pyrogram(bot, chat_id, lang)
        else:
            await bot.send_message(chat_id, await tr_block(lang, "❌ Library tidak dikenali."))
    except asyncio.CancelledError:
        await bot.send_message(chat_id, await tr_block(lang, "🛑 Proses dibatalkan."))
        raise
    except asyncio.TimeoutError:
        text = await tr_block(lang, "⏰ Waktu habis, kamu tidak merespon. Silakan ulangi dari menu.")
        await bot.send_message(chat_id, text, buttons=await back_to_menu_kb(lang))
    except Exception as e:
        text = await tr_block(lang, "❌ Terjadi kesalahan tak terduga:")
        await bot.send_message(
            chat_id,
            f"{text}\n`{type(e).__name__}: {e}`",
            buttons=await back_to_menu_kb(lang),
        )


async def _ask(bot, conv, lang, text, buttons=None):
    # PENTING: harus lewat conv.send_message() (bukan bot.send_message()
    # langsung), karena conv.get_response() menunggu balasan atas pesan
    # TERAKHIR yang dikirim melalui objek `conv` itu sendiri. Kalau kita
    # kirim lewat bot.send_message() biasa, Telethon tidak tahu pesan mana
    # yang harus ditunggu balasannya dan melempar
    # `ValueError: No message was sent previously`.
    translated = await tr_block(lang, text)
    btns = buttons if buttons is not None else await cancel_kb(lang)
    await conv.send_message(translated, buttons=btns)
    resp = await conv.get_response(timeout=CONVERSATION_TIMEOUT)
    if resp.raw_text.strip().lower() in CANCEL_WORDS:
        raise asyncio.CancelledError()
    return resp.raw_text.strip()


async def _send_success(bot, chat_id, lang, library_label: str, session_string: str):
    """Kirim hasil session string. Teks penjelasan diterjemahkan, tapi
    session_string SELALU dikirim mentah/apa adanya (lihat catatan di
    atas file ini)."""
    intro = await tr_block(lang, f"✅ **Session {library_label} berhasil dibuat!**")
    warning = await tr_block(
        lang,
        "⚠️ **JANGAN bagikan session string ini ke siapa pun.**\n"
        "Segera hapus pesan ini setelah kamu menyimpannya.",
    )
    await bot.send_message(
        chat_id,
        f"{intro}\n\n```\n{session_string}\n```\n\n{warning}",
        buttons=await back_to_menu_kb(lang),
    )


# ----------------------------------------------------------------------
# TELETHON FLOW
# ----------------------------------------------------------------------
async def _generate_telethon(bot, chat_id, lang: str):
    async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
        phone = await _ask(
            bot, conv, lang,
            "📱 **Kirim nomor telepon** akun Telegram kamu.\n"
            "Format: `+62812xxxxxxx` (pakai kode negara)\n\n"
            "Ketik /cancel untuk membatalkan.",
        )

        client = TelegramClient(StringSession(), SESSION_API_ID, SESSION_API_HASH)
        await client.connect()

        try:
            sent = await client.send_code_request(phone)
        except PhoneNumberInvalidError:
            await bot.send_message(chat_id, await tr_block(lang, "❌ Nomor telepon tidak valid. Silakan ulangi dari menu."))
            await client.disconnect()
            return
        except FloodWaitError as e:
            text = await tr_block(lang, "⏳ Kena flood wait, coba lagi setelah")
            await bot.send_message(chat_id, f"{text} {e.seconds} detik.")
            await client.disconnect()
            return

        code = await _ask(
            bot, conv, lang,
            "🔢 **Masukkan kode OTP** yang dikirim ke akun Telegram kamu.\n"
            "_Tips: pisahkan dengan spasi contoh `1 2 3 4 5` jika Telegram "
            "memblokir pengiriman kode utuh._",
        )
        code = code.replace(" ", "")

        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except PhoneCodeInvalidError:
            await bot.send_message(chat_id, await tr_block(lang, "❌ Kode OTP salah. Silakan ulangi dari menu."))
            await client.disconnect()
            return
        except PhoneCodeExpiredError:
            await bot.send_message(chat_id, await tr_block(lang, "❌ Kode OTP kedaluwarsa. Silakan ulangi dari menu."))
            await client.disconnect()
            return
        except SessionPasswordNeededError:
            for attempt in range(3):
                password = await _ask(
                    bot, conv, lang,
                    "🔐 Akun kamu memakai **verifikasi 2 langkah**.\n"
                    "Masukkan password kamu:",
                )
                try:
                    await client.sign_in(password=password)
                    break
                except PasswordHashInvalidError:
                    if attempt == 2:
                        await bot.send_message(chat_id, await tr_block(lang, "❌ Password salah 3x. Silakan ulangi dari menu."))
                        await client.disconnect()
                        return
                    await bot.send_message(chat_id, await tr_block(lang, "❌ Password salah, coba lagi."))

        session_string = client.session.save()
        await client.disconnect()
        await _send_success(bot, chat_id, lang, "Telethon", session_string)


# ----------------------------------------------------------------------
# PYROGRAM FLOW
# ----------------------------------------------------------------------
async def _generate_pyrogram(bot, chat_id, lang: str):
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
            bot, conv, lang,
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
            await bot.send_message(chat_id, await tr_block(lang, "❌ Nomor telepon tidak valid. Silakan ulangi dari menu."))
            await client.disconnect()
            return
        except FloodWait as e:
            text = await tr_block(lang, "⏳ Kena flood wait, coba lagi setelah")
            await bot.send_message(chat_id, f"{text} {e.value} detik.")
            await client.disconnect()
            return

        code = await _ask(
            bot, conv, lang,
            "🔢 **Masukkan kode OTP** yang dikirim ke akun Telegram kamu.\n"
            "_Tips: pisahkan dengan spasi contoh `1 2 3 4 5` jika Telegram "
            "memblokir pengiriman kode utuh._",
        )
        code = code.replace(" ", "")

        try:
            await client.sign_in(phone, sent.phone_code_hash, code)
        except PhoneCodeInvalid:
            await bot.send_message(chat_id, await tr_block(lang, "❌ Kode OTP salah. Silakan ulangi dari menu."))
            await client.disconnect()
            return
        except PhoneCodeExpired:
            await bot.send_message(chat_id, await tr_block(lang, "❌ Kode OTP kedaluwarsa. Silakan ulangi dari menu."))
            await client.disconnect()
            return
        except SessionPasswordNeeded:
            for attempt in range(3):
                password = await _ask(
                    bot, conv, lang,
                    "🔐 Akun kamu memakai **verifikasi 2 langkah**.\n"
                    "Masukkan password kamu:",
                )
                try:
                    await client.check_password(password)
                    break
                except PasswordHashInvalid:
                    if attempt == 2:
                        await bot.send_message(chat_id, await tr_block(lang, "❌ Password salah 3x. Silakan ulangi dari menu."))
                        await client.disconnect()
                        return
                    await bot.send_message(chat_id, await tr_block(lang, "❌ Password salah, coba lagi."))

        session_string = await client.export_session_string()
        await client.disconnect()
        await _send_success(bot, chat_id, lang, "Pyrogram", session_string)
