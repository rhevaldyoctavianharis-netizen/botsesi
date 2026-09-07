"""
config.py
Semua konfigurasi bot diambil dari file .env
Silakan copy .env.example -> .env lalu isi sesuai data kamu.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int = 0) -> int:
    val = os.getenv(name, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _get_int_list(name: str):
    """Parse env berisi angka dipisah koma, contoh: '123,456,789' -> [123, 456, 789]."""
    raw = os.getenv(name, "")
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return result


# ==== Kredensial BOT ====
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# API ID & HASH punya BOT (dipakai bot untuk konek ke Telegram)
API_ID = _get_int("API_ID")
API_HASH = os.getenv("API_HASH", "")

# ==== Kredensial dipakai untuk GENERATE SESSION user ====
# Default: pakai API_ID/API_HASH yang sama dengan bot.
# Bisa diganti kredensial khusus kalau mau dipisah.
SESSION_API_ID = _get_int("SESSION_API_ID", API_ID)
SESSION_API_HASH = os.getenv("SESSION_API_HASH", API_HASH)

# ==== Force Join Channel (nilai awal / seed, sisanya dikelola via /admin) ====
FORCE_JOIN = os.getenv("FORCE_JOIN", "true").lower() == "true"
# Username channel tanpa "@", contoh: "channel_saya"
ADMIN_CHANNEL = os.getenv("ADMIN_CHANNEL", "")
ADMIN_CHANNEL_URL = os.getenv("ADMIN_CHANNEL_URL", f"https://t.me/{ADMIN_CHANNEL}" if ADMIN_CHANNEL else "")

# ==== Admin Panel ====
# User ID Telegram yang boleh akses /admin. Pisahkan dengan koma kalau lebih dari satu.
# Contoh: ADMIN_IDS=111111111,222222222
ADMIN_IDS = _get_int_list("ADMIN_IDS")

# ==== Info Owner / Pembuat Bot ====
OWNER_NAME = os.getenv("OWNER_NAME", "Admin")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "admin")

# ==== Lain-lain ====
CONVERSATION_TIMEOUT = _get_int("CONVERSATION_TIMEOUT", 300)  # detik
BANNER_PATH = os.path.join(os.path.dirname(__file__), "assets", "banner.png")

# ==== Render.com / deployment ====
# Render.com otomatis mengisi $PORT. Web server keep-alive (lihat keep_alive.py)
# akan bind ke port ini supaya Render mendeteksi service sebagai "live".
PORT = _get_int("PORT", 8080)

# Lokasi file penyimpanan pengaturan live (bisa diubah admin lewat /admin
# tanpa restart bot). Lihat utils/db.py & utils/settings.py.
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
