"""
utils/db.py
Penyimpanan sederhana berbasis file JSON untuk pengaturan bot yang bisa
diubah admin secara live lewat /admin (tanpa perlu restart / redeploy).

Catatan penting untuk deploy di Render.com:
Disk di Render bersifat ephemeral untuk plan gratis (isi file akan hilang
setiap kali service di-redeploy, tapi TETAP AMAN selama service hanya
restart/sleep-wake biasa). Untuk penyimpanan yang benar-benar permanen
lintas redeploy, pertimbangkan Render Persistent Disk (paid) atau
pindahkan ke database eksternal.
"""

import json
import os
import threading

from config import SETTINGS_PATH, DATA_DIR

_LOCK = threading.Lock()

_DEFAULT = {
    "force_join_enabled": True,
    # list of {"username": str, "url": str, "label": str}
    "force_join_channels": [],
    "telethon_enabled": True,
    "pyrogram_enabled": True,
    "maintenance_mode": False,
    "welcome_text": None,
    "about_text": None,
    "extra_admin_ids": [],
    "users": [],
    # user_id (str) -> kode bahasa ISO 639-1, contoh: {"8588390695": "en"}
    "user_languages": {},
}


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT, f, indent=2, ensure_ascii=False)


def _load() -> dict:
    _ensure_file()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}
    return {**_DEFAULT, **data}


def _save(data: dict) -> None:
    tmp_path = SETTINGS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, SETTINGS_PATH)


def get_all() -> dict:
    with _LOCK:
        return _load()


def get(key: str, default=None):
    with _LOCK:
        return _load().get(key, default)


def set(key: str, value) -> dict:
    with _LOCK:
        data = _load()
        data[key] = value
        _save(data)
        return data


def update(mutator) -> dict:
    """mutator: fungsi(data: dict) -> None, memodifikasi data secara in-place."""
    with _LOCK:
        data = _load()
        mutator(data)
        _save(data)
        return data
