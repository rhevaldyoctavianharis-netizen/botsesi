"""
handlers/callbacks.py  (DIUBAH — translate nyata)
Menangani callback tombol untuk membuka menu pilihan library dan
mendispatch proses generate session sebagai BACKGROUND TASK, supaya bot
tetap responsif melayani user lain. Semua teks & tombol sekarang
diterjemahkan ke bahasa pilihan user lewat utils/i18n.py.
"""

import asyncio

from telethon import events

from utils.keyboards import choose_library_kb, back_to_menu_kb, join_channel_kb
from utils.force_join import get_unjoined_channels
from utils import state, settings
from utils.i18n import tr_block
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
        lang = settings.get_user_language(user.id)

        if settings.maintenance_mode() and not settings.is_admin(user.id):
            await event.answer(await tr_block(lang, "🛠️ Bot sedang maintenance, coba lagi nanti."), alert=True)
            return

        unjoined = await get_unjoined_channels(bot, user.id)
        if unjoined:
            await event.answer(await tr_block(lang, "❌ Kamu wajib join channel/grup dulu!"), alert=True)
            text = await tr_block(lang, "🔒 Kamu belum join semua channel/grup yang diwajibkan.")
            await event.edit(text, buttons=await join_channel_kb(unjoined, lang))
            return

        text = CHOOSE_LIB_TEXT
        if not settings.telethon_enabled():
            text += "\n⚠️ _Telethon sedang dinonaktifkan admin._"
        if not settings.pyrogram_enabled():
            text += "\n⚠️ _Pyrogram sedang dinonaktifkan admin._"
        text = await tr_block(lang, text)
        await event.edit(text, buttons=await choose_library_kb(lang))

    @bot.on(events.CallbackQuery(pattern=b"gen:telethon"))
    async def gen_telethon_cb(event):
        lang = settings.get_user_language(event.sender_id)
        if not settings.telethon_enabled():
            await event.answer(await tr_block(lang, "❌ Fitur Telethon sedang dinonaktifkan admin."), alert=True)
            return
        await _dispatch_generate(bot, event, "telethon", lang)

    @bot.on(events.CallbackQuery(pattern=b"gen:pyrogram"))
    async def gen_pyrogram_cb(event):
        lang = settings.get_user_language(event.sender_id)
        if not settings.pyrogram_enabled():
            await event.answer(await tr_block(lang, "❌ Fitur Pyrogram sedang dinonaktifkan admin."), alert=True)
            return
        await _dispatch_generate(bot, event, "pyrogram", lang)

    @bot.on(events.CallbackQuery(pattern=b"gen:cancel"))
    async def gen_cancel_cb(event):
        user_id = event.sender_id
        lang = settings.get_user_language(user_id)
        cancelled = state.cancel_task(user_id)
        if cancelled:
            await event.answer(await tr_block(lang, "🛑 Proses dibatalkan."))
            text = await tr_block(lang, "🛑 Proses generate session dibatalkan.")
            await event.edit(text, buttons=await back_to_menu_kb(lang))
        else:
            await event.answer(await tr_block(lang, "Tidak ada proses yang berjalan."))


async def _dispatch_generate(bot, event, library: str, lang: str):
    user_id = event.sender_id

    if state.is_busy(user_id):
        await event.answer(await tr_block(lang, "⚠️ Kamu masih punya proses generate yang berjalan!"), alert=True)
        return

    starting = await tr_block(lang, f"Memulai proses {library.title()}...")
    await event.answer(starting)

    # ==== BACKGROUND TASK ====
    # asyncio.create_task membuat proses generate session (yang butuh
    # menunggu input user: nomor telpon, OTP, password) berjalan sebagai
    # task independen. Event loop TIDAK diblok, sehingga user lain tetap
    # bisa dilayani bot secara bersamaan.
    task = asyncio.create_task(run_generate_session(bot, event, library, lang))
    state.register_task(user_id, task)
