"""
handlers/language.py
Menu pilihan bahasa (tombol 🌐 Bahasa di menu utama). Semua ~180 kode
bahasa ISO 639-1 tersedia (lihat utils/languages.py) lewat menu
berpaginasi. Begitu user memilih, preferensinya disimpan PERMANEN ke
data/settings.json lewat utils/settings — jadi tidak akan reset walau
bot restart, redeploy, atau user membuka ulang bot kapan pun (selama
disknya sendiri tidak dihapus, lihat catatan di README soal ephemeral
disk Render free plan).
"""

from telethon import events

from utils import settings
from utils.languages import LANGUAGE_MAP
from utils.translations import lang_saved_text
from utils.keyboards import language_menu_kb, back_to_menu_kb


def register(bot):
    @bot.on(events.CallbackQuery(pattern=b"menu:lang"))
    async def lang_menu_cb(event):
        current = settings.get_user_language(event.sender_id)
        current_name = LANGUAGE_MAP.get(current, current)
        await event.edit(
            f"🌐 **Pilih Bahasa**\n\n"
            f"Bahasa saat ini: **{current_name}** (`{current}`)\n\n"
            "Pilih bahasa yang kamu inginkan di bawah ini. Pilihan kamu "
            "akan diingat bot secara permanen.",
            buttons=language_menu_kb(0),
        )

    @bot.on(events.CallbackQuery(pattern=b"lang:page:"))
    async def lang_page_cb(event):
        page = int(event.data.decode().split(":")[-1])
        await event.edit(buttons=language_menu_kb(page))

    @bot.on(events.CallbackQuery(pattern=b"lang:noop"))
    async def lang_noop_cb(event):
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=b"lang:set:"))
    async def lang_set_cb(event):
        code = event.data.decode().split(":", 2)[-1]
        name = LANGUAGE_MAP.get(code, code)
        settings.set_user_language(event.sender_id, code)
        await event.answer(f"✅ {name}")
        await event.edit(lang_saved_text(code, name), buttons=back_to_menu_kb())
