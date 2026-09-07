"""
utils/translate.py  (BARU)
Engine translate otomatis pakai Google Translate lewat library
`deep-translator`, dengan cache permanen (memori + file JSON) supaya
teks yang sama tidak diterjemahkan berulang-ulang lewat internet.

Kenapa deep-translator, bukan `googletrans`? `googletrans` sering rusak
karena bergantung pada endpoint internal Google yang berubah-ubah tanpa
pemberitahuan. `deep-translator` lebih stabil dan aktif di-maintain,
sama-sama pakai Google Translate sebagai mesinnya.

SEMUA kegagalan (tidak ada internet dari server, kode bahasa tidak
dikenali Google Translate, dsb) FAIL-OPEN: kembalikan teks aslinya,
JANGAN sampai bikin bot crash. utils/languages.py punya 183 kode bahasa
ISO 639-1, tapi Google Translate sendiri tidak mendukung semuanya
(terutama bahasa historis/konstruksi seperti Church Slavic, Avestan,
Herero, dll) — untuk kode yang tidak didukung, translate() otomatis
fallback ke teks sumber (Bahasa Indonesia) alih-alih error.
"""

import asyncio
import hashlib
import json
import os
import threading

from config import DATA_DIR

_CACHE_PATH = os.path.join(DATA_DIR, "translation_cache.json")
_LOCK = threading.Lock()
_MEM_CACHE = {}

try:
    from deep_translator import GoogleTranslator
    _ENGINE_AVAILABLE = True
except ImportError:
    # deep-translator belum ke-install -> bot tetap jalan, semua translate
    # otomatis dianggap "gagal" dan fallback ke teks asli.
    _ENGINE_AVAILABLE = False


def _cache_key(text: str, lang: str) -> str:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return f"{lang}:{h}"


def _load_cache() -> dict:
    if not os.path.exists(_CACHE_PATH):
        return {}
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, _CACHE_PATH)


def _translate_blocking(text: str, target_lang: str, source_lang: str) -> str:
    """Bagian yang benar-benar hit jaringan ke Google Translate. HARUS
    dipanggil lewat asyncio.to_thread() (lihat translate() di bawah)
    supaya tidak memblokir event loop bot saat menunggu respons jaringan."""
    if not _ENGINE_AVAILABLE:
        return text
    try:
        result = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
        return result or text
    except Exception:
        return text


async def translate(text: str, target_lang: str, source_lang: str = "id") -> str:
    """Translate satu string. Cache-first (instan kalau sudah pernah
    diterjemahkan sebelumnya), baru hit jaringan kalau belum ada di cache."""
    if not text or not target_lang or target_lang == source_lang:
        return text

    key = _cache_key(text, target_lang)

    with _LOCK:
        if key in _MEM_CACHE:
            return _MEM_CACHE[key]
        cache = _load_cache()
        if key in cache:
            _MEM_CACHE[key] = cache[key]
            return cache[key]

    result = await asyncio.to_thread(_translate_blocking, text, target_lang, source_lang)

    with _LOCK:
        _MEM_CACHE[key] = result
        cache = _load_cache()
        cache[key] = result
        _save_cache(cache)

    return result
