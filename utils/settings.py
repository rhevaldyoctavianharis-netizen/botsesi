"""
utils/settings.py
Lapisan API tingkat-tinggi di atas utils/db.py. Semua handler (start,
callbacks, admin) berbicara ke modul ini, bukan langsung ke db.py,
supaya logic default & validasi terpusat di satu tempat.

Ini yang membuat admin bisa "kontrol 100%": setiap toggle / channel /
teks pesan / status maintenance dibaca dari sini secara live setiap
kali dibutuhkan, jadi perubahan admin langsung berlaku tanpa restart bot.
"""

from config import ADMIN_IDS
from utils import db


# ---------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------
def is_admin(user_id: int) -> bool:
    extra = db.get("extra_admin_ids", [])
    return user_id in ADMIN_IDS or user_id in extra


def add_admin(user_id: int) -> None:
    def _mut(data):
        if user_id not in data["extra_admin_ids"] and user_id not in ADMIN_IDS:
            data["extra_admin_ids"].append(user_id)

    db.update(_mut)


def remove_admin(user_id: int) -> None:
    def _mut(data):
        if user_id in data.get("extra_admin_ids", []):
            data["extra_admin_ids"].remove(user_id)

    db.update(_mut)


def list_admins():
    """Gabungan admin dari .env (ADMIN_IDS, tidak bisa dihapus lewat bot)
    dan admin tambahan yang didaftarkan lewat /admin."""
    return sorted(set(ADMIN_IDS) | set(db.get("extra_admin_ids", [])))


def is_env_admin(user_id: int) -> bool:
    """True kalau admin ini berasal dari .env (tidak bisa dihapus lewat panel)."""
    return user_id in ADMIN_IDS


# ---------------------------------------------------------------------
# USER TRACKING (untuk broadcast & statistik)
# ---------------------------------------------------------------------
def track_user(user_id: int) -> None:
    def _mut(data):
        if user_id not in data["users"]:
            data["users"].append(user_id)

    db.update(_mut)


def all_users():
    return db.get("users", [])


# ---------------------------------------------------------------------
# FORCE JOIN
# ---------------------------------------------------------------------
def force_join_enabled() -> bool:
    return db.get("force_join_enabled", True)


def set_force_join_enabled(value: bool) -> None:
    db.set("force_join_enabled", value)


def force_join_channels():
    return db.get("force_join_channels", [])


def add_force_join_channel(username: str, url: str, label: str = None) -> None:
    def _mut(data):
        channels = data.setdefault("force_join_channels", [])
        if any(c["username"].lower() == username.lower() for c in channels):
            return
        channels.append({"username": username, "url": url, "label": label or username})

    db.update(_mut)


def remove_force_join_channel(username: str) -> None:
    def _mut(data):
        data["force_join_channels"] = [
            c for c in data.get("force_join_channels", [])
            if c["username"].lower() != username.lower()
        ]

    db.update(_mut)


# ---------------------------------------------------------------------
# FITUR GENERATE (Telethon / Pyrogram on-off)
# ---------------------------------------------------------------------
def telethon_enabled() -> bool:
    return db.get("telethon_enabled", True)


def pyrogram_enabled() -> bool:
    return db.get("pyrogram_enabled", True)


def set_feature(name: str, value: bool) -> None:
    db.set(name, value)


# ---------------------------------------------------------------------
# MODE MAINTENANCE
# ---------------------------------------------------------------------
def maintenance_mode() -> bool:
    return db.get("maintenance_mode", False)


def set_maintenance_mode(value: bool) -> None:
    db.set("maintenance_mode", value)


# ---------------------------------------------------------------------
# TEKS PESAN (welcome / about) — bisa diedit admin, None = pakai default
# ---------------------------------------------------------------------
def welcome_text(default: str) -> str:
    custom = db.get("welcome_text")
    return custom if custom else default


def set_welcome_text(text) -> None:
    db.set("welcome_text", text)


def about_text(default: str) -> str:
    custom = db.get("about_text")
    return custom if custom else default


def set_about_text(text) -> None:
    db.set("about_text", text)


# ---------------------------------------------------------------------
# BAHASA PER-USER — persisten, tidak reset walau bot restart / user
# buka bot lagi kapan pun. Disimpan sebagai {"<user_id>": "<kode>"}.
# ---------------------------------------------------------------------
def has_user_language(user_id: int) -> bool:
    return str(user_id) in db.get("user_languages", {})


def get_user_language(user_id: int, default: str = "id") -> str:
    return db.get("user_languages", {}).get(str(user_id), default)


def set_user_language(user_id: int, code: str) -> None:
    def _mut(data):
        data.setdefault("user_languages", {})[str(user_id)] = code

    db.update(_mut)
