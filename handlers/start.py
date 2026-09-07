"""
handlers/start.py
Menangani /start, force-join check (multi channel, live dari admin),
mode maintenance, dan menu "Tentang Bot". Teks welcome/about bisa
diedit admin lewat /admin dan langsung berlaku tanpa restart bot.
"""

from telethon import events

from config import OWNER_NAME, OWNER_USERNAME, BANNER_PATH
from utils.force_join import get_unjoined_channels
from utils import settings
from utils.languages import LANGUAGE_MAP
from utils.keyboards import join_channel_kb, main_menu_kb, back_to_menu_kb

DEFAULT_WELCOME_TEXT = f"""
👋 **Halo, {{name}}!**

Selamat datang di **Session Generator Bot** — bot untuk generate
**session string** akun Telegram kamu secara aman & interaktif.

🧑‍💻 **Dibuat oleh:** [{OWNER_NAME}](https://t.me/{OWNER_USERNAME})
📚 **Library digunakan:** `Telethon` & `Pyrogram`

**Cara pakai:**
1️⃣ Tekan tombol **Generate Session Now**
2️⃣ Pilih library yang kamu inginkan (Telethon / Pyrogram)
3️⃣ Ikuti instruksi: kirim nomor telepon → kode OTP → password (jika ada)
4️⃣ Session string langsung dikirim ke chat ini

⚠️ **Peringatan Keamanan:**
Session string setara dengan password akun kamu. **Jangan pernah**
membagikannya ke siapa pun, termasuk admin bot ini.

Silakan pilih menu di bawah 👇
"""

DEFAULT_ABOUT_TEXT = f"""
ℹ️ **Tentang Bot Ini**

Bot ini membantu kamu membuat **session string** untuk userbot/self-bot
menggunakan library **Telethon** atau **Pyrogram**, langsung lewat chat
Telegram tanpa perlu setup lokal.

🧑‍💻 Dibuat oleh: [{OWNER_NAME}](https://t.me/{OWNER_USERNAME})
📚 Library: `Telethon`, `Pyrogram`
⚙️ Arsitektur: async background task (multi-user friendly)

Gunakan dengan bijak dan jangan bagikan session string ke pihak
yang tidak dipercaya.
"""

JOIN_REQUIRED_TEXT = """
🔒 **Akses Terbatas**

Untuk menggunakan bot ini, kamu **wajib join channel/grup** berikut terlebih dahulu.

Setelah join semua, tekan tombol **"Saya Sudah Join"** di bawah untuk verifikasi.
"""

MAINTENANCE_TEXT = """
🛠️ **Bot Sedang Maintenance**

Mohon maaf, bot sedang dalam perbaikan oleh admin. Silakan coba lagi nanti.
"""


def _render(template: str, name: str) -> str:
    # Pakai replace (bukan .format) supaya teks custom dari admin yang
    # kebetulan mengandung karakter "{" atau "}" lain tidak bikin error.
    return template.replace("{name}", name)


def register(bot):
    @bot.on(events.NewMessage(pattern="/start"))
    async def start_handler(event):
        user = await event.get_sender()
        name = user.first_name or "Kamu"
        settings.track_user(user.id)

        # Deteksi bahasa HANYA sekali (saat pertama kali /start). Setelah
        # itu preferensi user tersimpan permanen dan TIDAK akan tertimpa
        # lagi walau lang_code Telegram-nya berubah atau bot di-restart —
        # user hanya bisa menggantinya lewat menu 🌐 Bahasa.
        if not settings.has_user_language(user.id):
            detected = getattr(user, "lang_code", None)
            settings.set_user_language(user.id, detected if detected in LANGUAGE_MAP else "id")

        if settings.maintenance_mode() and not settings.is_admin(user.id):
            await event.respond(MAINTENANCE_TEXT)
            return

        unjoined = await get_unjoined_channels(bot, user.id)
        if unjoined:
            await event.respond(JOIN_REQUIRED_TEXT, buttons=join_channel_kb(unjoined))
            return

        await _send_welcome(event, name)

    @bot.on(events.CallbackQuery(pattern=b"check_join"))
    async def check_join_cb(event):
        user = await event.get_sender()
        unjoined = await get_unjoined_channels(bot, user.id)
        if not unjoined:
            await event.answer("✅ Verifikasi berhasil!")
            name = user.first_name or "Kamu"
            text = _render(settings.welcome_text(DEFAULT_WELCOME_TEXT), name)
            await event.edit(text, buttons=main_menu_kb(), link_preview=False)
        else:
            await event.answer("❌ Kamu masih belum join semua channel/grup!", alert=True)
            await event.edit(JOIN_REQUIRED_TEXT, buttons=join_channel_kb(unjoined))

    @bot.on(events.CallbackQuery(pattern=b"menu:back"))
    async def back_cb(event):
        user = await event.get_sender()
        name = user.first_name or "Kamu"
        text = _render(settings.welcome_text(DEFAULT_WELCOME_TEXT), name)
        await event.edit(text, buttons=main_menu_kb(), link_preview=False)

    @bot.on(events.CallbackQuery(pattern=b"menu:about"))
    async def about_cb(event):
        await event.edit(
            settings.about_text(DEFAULT_ABOUT_TEXT),
            buttons=back_to_menu_kb(),
            link_preview=False,
        )


async def _send_welcome(event, name):
    text = _render(settings.welcome_text(DEFAULT_WELCOME_TEXT), name)
    try:
        await event.respond(file=BANNER_PATH, message=text, buttons=main_menu_kb())
    except Exception:
        # fallback kalau banner.png tidak ditemukan / gagal upload
        await event.respond(text, buttons=main_menu_kb(), link_preview=False)
