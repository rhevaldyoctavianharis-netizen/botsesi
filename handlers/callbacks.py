"""
handlers/callbacks.py
Menangani callback tombol untuk membuka menu pilihan library dan
mendispatch proses generate session sebagai BACKGROUND TASK, supaya bot
tetap responsif melayani user lain. Sekarang juga menghormati toggle
admin: force-join (multi channel), on/off per-library, dan mode
maintenance — semua dicek live dari utils/settings.
"""

import asyncio

from telethon import events

from utils.keyboards import choose_library_kb, back_to_menu_kb, join_channel_kb
from utils.force_join import get_unjoined_channels
from utils import state, settings
from handlers.session_gen import run_generate_session

CHOOSE_LIB_TEXT = """
🔑 **Generate Session**

Pilih library yang ingin kamu gunakan untuk generate session string:

🟦 **Telethon** — cocok untuk userbot berbasis Telethon
🟩 **Pyrogram** — cocok untuk userbot berbasis Pyrogram
"""


def register(bot):
    @bot.on(events.CallbackQuery(pattern=b"menu:generate"))
    async def generate_menu_cb(event):
        user = await event.get_sender()

        if settings.maintenance_mode() and not settings.is_admin(user.id):
            await event.answer("🛠️ Bot sedang maintenance, coba lagi nanti.", alert=True)
            return

        unjoined = await get_unjoined_channels(bot, user.id)
        if unjoined:
            await event.answer("❌ Kamu wajib join channel/grup dulu!", alert=True)
            await event.edit(
                "🔒 Kamu belum join semua channel/grup yang diwajibkan.",
                buttons=join_channel_kb(unjoined),
            )
            return

        text = CHOOSE_LIB_TEXT
        if not settings.telethon_enabled():
            text += "\n⚠️ _Telethon sedang dinonaktifkan admin._"
        if not settings.pyrogram_enabled():
            text += "\n⚠️ _Pyrogram sedang dinonaktifkan admin._"
        await event.edit(text, buttons=choose_library_kb())

    @bot.on(events.CallbackQuery(pattern=b"gen:telethon"))
    async def gen_telethon_cb(event):
        if not settings.telethon_enabled():
            await event.answer("❌ Fitur Telethon sedang dinonaktifkan admin.", alert=True)
            return
        await _dispatch_generate(bot, event, "telethon")

    @bot.on(events.CallbackQuery(pattern=b"gen:pyrogram"))
    async def gen_pyrogram_cb(event):
        if not settings.pyrogram_enabled():
            await event.answer("❌ Fitur Pyrogram sedang dinonaktifkan admin.", alert=True)
            return
        await _dispatch_generate(bot, event, "pyrogram")

    @bot.on(events.CallbackQuery(pattern=b"gen:cancel"))
    async def gen_cancel_cb(event):
        user_id = event.sender_id
        cancelled = state.cancel_task(user_id)
        if cancelled:
            await event.answer("🛑 Proses dibatalkan.")
            await event.edit("🛑 Proses generate session dibatalkan.", buttons=back_to_menu_kb())
        else:
            await event.answer("Tidak ada proses yang berjalan.")


async def _dispatch_generate(bot, event, library: str):
    user_id = event.sender_id

    if state.is_busy(user_id):
        await event.answer("⚠️ Kamu masih punya proses generate yang berjalan!", alert=True)
        return

    await event.answer(f"Memulai proses {library.title()}...")

    # ==== BACKGROUND TASK ====
    # asyncio.create_task membuat proses generate session (yang butuh
    # menunggu input user: nomor telpon, OTP, password) berjalan sebagai
    # task independen. Event loop TIDAK diblok, sehingga user lain tetap
    # bisa dilayani bot secara bersamaan.
    task = asyncio.create_task(run_generate_session(bot, event, library))
    state.register_task(user_id, task)
