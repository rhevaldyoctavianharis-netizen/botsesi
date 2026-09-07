"""
handlers/language.py  (DIUBAH — translate dinamis untuk SEMUA 183 bahasa)
Menu pilihan bahasa (tombol 🌐 Bahasa di menu utama). Begitu user
memilih, preferensinya disimpan PERMANEN ke data/settings.json lewat
utils/settings — tidak akan reset walau bot restart, redeploy, atau
user membuka ulang bot kapan pun.

Pesan konfirmasi setelah memilih bahasa sekarang memakai dua lapis:
1. Kalau kodenya ada di utils/translations.LANG_SAVED (~20 bahasa yang
   sudah dicek kualitasnya manual) -> pakai teks itu, instan & akurat.
2. Kalau tidak ada -> translate otomatis lewat Google Translate
   (utils/i18n.tr_block), tetap jalan untuk SEMUA 183 kode bahasa tanpa
   terkecuali.
"""

from telethon import events

from utils import settings
from utils.languages import LANGUAGE_MAP
from utils.translations import LANG_SAVED
from utils.i18n import tr_block
from utils.keyboards import language_menu_kb, back_to_menu_kb


def register(bot):
    @bot.on(events.CallbackQuery(pattern=b"menu:lang"))
    async def lang_menu_cb(event):
        lang = settings.get_user_language(event.sender_id)
        current_name = LANGUAGE_MAP.get(lang, lang)
        text = await tr_block(
            lang,
            f"🌐 **Pilih Bahasa**\n\nBahasa saat ini: **{current_name}**\n\n"
            "Pilih bahasa yang kamu inginkan di bawah ini. Pilihan kamu "
            "akan diingat bot secara permanen.",
        )
        await event.edit(text, buttons=await language_menu_kb(0, lang=lang))

    @bot.on(events.CallbackQuery(pattern=b"lang:page:"))
    async def lang_page_cb(event):
        lang = settings.get_user_language(event.sender_id)
        page = int(event.data.decode().split(":")[-1])
        await event.edit(buttons=await language_menu_kb(page, lang=lang))

    @bot.on(events.CallbackQuery(pattern=b"lang:noop"))
    async def lang_noop_cb(event):
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=b"lang:set:"))
    async def lang_set_cb(event):
        code = event.data.decode().split(":", 2)[-1]
        name = LANGUAGE_MAP.get(code, code)
        settings.set_user_language(event.sender_id, code)
        await event.answer(f"✅ {name}")

        if code in LANG_SAVED:
            text = LANG_SAVED[code]
        else:
            text = await tr_block(code, f"✅ Bahasa berhasil diatur ke **{name}**.")

        await event.edit(text, buttons=await back_to_menu_kb(code))
