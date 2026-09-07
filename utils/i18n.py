"""
utils/i18n.py  (BARU)
Lapisan terjemahan terpusat yang dipakai seluruh handler & keyboard.
Semua teks sumber ditulis dalam Bahasa Indonesia di titik pemanggilan,
lalu diterjemahkan on-the-fly ke bahasa pilihan user lewat
utils/translate.py (Google Translate + cache).

- tr(lang, text)          -> translate 1 string
- tr_many(lang, [a, b])   -> translate banyak string SEKALIGUS (paralel,
                             pakai asyncio.gather) -- dipakai untuk label
                             tombol supaya tidak translate satu-satu
- tr_block(lang, text)    -> translate teks MULTI-BARIS per baris (biar
                             struktur baris/baris kosong & markdown tetap
                             terjaga), dipakai untuk paragraf panjang
                             seperti welcome/about/pesan error

PENTING: fungsi-fungsi ini HANYA untuk teks yang tampil ke user (label
tombol, judul, isi pesan). JANGAN PERNAH memasukkan data sensitif ke
sini (session string, token, dsb) -- lihat catatan di
handlers/session_gen.py soal ini.
"""

import asyncio

from utils.translate import translate


async def tr(lang: str, text: str, source_lang: str = "id") -> str:
    return await translate(text, lang, source_lang)


async def tr_many(lang: str, texts, source_lang: str = "id"):
    if lang == source_lang:
        return list(texts)
    return await asyncio.gather(*(translate(t, lang, source_lang) for t in texts))


async def _identity(x):
    return x


async def tr_block(lang: str, text: str, source_lang: str = "id") -> str:
    if not text or lang == source_lang:
        return text
    lines = text.split("\n")
    coros = [
        translate(line, lang, source_lang) if line.strip() else _identity(line)
        for line in lines
    ]
    translated = await asyncio.gather(*coros)
    return "\n".join(translated)
