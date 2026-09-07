"""
main.py
Entry point bot. Menjalankan TelegramClient (Telethon) sebagai bot,
mendaftarkan semua handler modular (termasuk panel admin), lalu
menjalankan web server keep-alive kecil supaya bisa dideploy sebagai
Web Service di Render.com.

Jalankan lokal dengan:
    python main.py
"""

import asyncio
import logging

from telethon import TelegramClient

from config import BOT_TOKEN, API_ID, API_HASH, ADMIN_CHANNEL, ADMIN_CHANNEL_URL
from handlers import start, callbacks, admin, language
from utils import settings
from keep_alive import start_keep_alive

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("session-bot")


def _migrate_legacy_env_channel():
    """Kalau ADMIN_CHANNEL diisi lewat .env (cara lama, single channel)
    dan belum ada di daftar force-join settings (JSON live), migrasikan
    otomatis sekali saja — supaya perilaku lama tetap jalan tanpa perlu
    admin setting ulang manual lewat /admin setelah update ini."""
    if not ADMIN_CHANNEL:
        return
    channels = settings.force_join_channels()
    if any(c["username"].lower() == ADMIN_CHANNEL.lower() for c in channels):
        return
    settings.add_force_join_channel(ADMIN_CHANNEL, ADMIN_CHANNEL_URL, ADMIN_CHANNEL)


async def main():
    if not BOT_TOKEN or not API_ID or not API_HASH:
        raise SystemExit(
            "❌ BOT_TOKEN / API_ID / API_HASH belum di-set. "
            "Copy .env.example jadi .env lalu isi datanya (atau set Environment "
            "Variables di dashboard Render.com)."
        )

    _migrate_legacy_env_channel()

    # ==== OPTIMASI CONCURRENCY (biar tidak antre saat banyak user) ====
    # sequential_updates=False -> setiap update (pesan/klik tombol) dari
    # Telegram di-dispatch sebagai task asyncio TERPISAH oleh Telethon,
    # bukan diproses satu-satu secara berurutan. Digabung dengan pola
    # asyncio.create_task() yang sudah dipakai untuk proses generate
    # session & flow admin (lihat handlers/callbacks.py & handlers/admin.py),
    # ini membuat banyak user bisa diproses BERSAMAAN dalam satu sesi bot,
    # tanpa saling menunggu. Catatan: ini concurrency berbasis asyncio
    # (single-thread, cooperative), bukan multi-threading OS — tapi untuk
    # I/O-bound seperti bot Telegram, ini sudah maksimal secara wajar.
    bot = TelegramClient(
        "bot_session",
        API_ID,
        API_HASH,
        sequential_updates=False,
        connection_retries=5,
        retry_delay=1,
    )
    await bot.start(bot_token=BOT_TOKEN)

    # Daftarkan semua handler modular
    start.register(bot)
    callbacks.register(bot)
    admin.register(bot)
    language.register(bot)

    # Web server kecil supaya Render.com (Web Service) mendeteksi port terbuka.
    # Tidak berpengaruh apa-apa saat dijalankan lokal / sebagai Background Worker.
    await start_keep_alive()

    logger.info("✅ Bot berhasil dijalankan. Menunggu pesan...")
    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
