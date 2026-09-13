"""
handlers/whatsapp_gen.py  (BARU)
Generate session WhatsApp Multi-Device pakai Baileys (Node.js),
dipanggil sebagai SUBPROCESS terpisah per user dari whatsapp/pair.js.

Alur:
1. User kirim nomor WhatsApp (dengan kode negara)
2. Bot spawn `node whatsapp/pair.js <nomor> <folder_sesi_unik>`
3. Node balikin PAIRING_CODE:xxxxxx lewat stdout -> bot kirim ke user,
   minta dimasukkan di WhatsApp: Setelan -> Perangkat Tertaut ->
   Tautkan dengan nomor telepon
4. Bot tunggu sinyal CONNECTED / ERROR / TIMEOUT dari proses Node
5. Kalau CONNECTED -> user PILIH SENDIRI lewat tombol: Multi File (ZIP,
   struktur asli Baileys) atau Single File (satu JSON gabungan)
6. Folder sesi SELALU dihapus setelah selesai (berhasil/gagal/timeout/
   dibatalkan) -- file kredensial WhatsApp itu setara password akun,
   tidak boleh nyangkut di disk server lebih lama dari perlu.

PENTING SOAL TRANSLATE: sama seperti session Telegram, isi file
kredensial (JSON WhatsApp) TIDAK PERNAH dilewatkan ke translate --
cuma teks penjelasan di sekitarnya yang diterjemahkan.

PENTING SOAL CONCURRENCY: proses Node adalah subprocess PENDEK per
sesi (bukan servis long-running terpisah), dijalankan lewat
asyncio.create_subprocess_exec yang non-blocking -- jadi banyak user
bisa generate WhatsApp session BERSAMAAN tanpa saling ganggu, sama
seperti generate session Telegram.
"""

import asyncio
import json
import os
import shutil
import uuid
import zipfile

from telethon import events, Button

from config import CONVERSATION_TIMEOUT
from utils.keyboards import cancel_kb, back_to_menu_kb
from utils.i18n import tr_block, tr_many

CANCEL_WORDS = {"/cancel", "batal", "cancel"}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHATSAPP_SCRIPT = os.path.join(BASE_DIR, "whatsapp", "pair.js")
SESSIONS_ROOT = os.path.join(BASE_DIR, "data", "wa_sessions")

PAIRING_TIMEOUT = 130  # detik -- sedikit di atas TIMEOUT_MS (120 detik) di pair.js
FORMAT_CHOICE_TIMEOUT = 60  # detik menunggu user pilih tombol format file


async def run_generate_whatsapp(bot, event, lang: str = "id"):
    chat_id = event.chat_id
    os.makedirs(SESSIONS_ROOT, exist_ok=True)
    session_dir = os.path.join(SESSIONS_ROOT, f"{chat_id}_{uuid.uuid4().hex[:8]}")
    proc = None

    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            phone = await _ask(
                bot, conv, lang,
                "📱 **Kirim nomor WhatsApp** yang mau ditautkan.\n"
                "Format: `+62812xxxxxxx` (pakai kode negara)\n\n"
                "Ketik /cancel untuk membatalkan.",
            )

            os.makedirs(session_dir, exist_ok=True)

            proc = await asyncio.create_subprocess_exec(
                "node", WHATSAPP_SCRIPT, phone, session_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            connected, error_msg = await _watch_pairing(bot, chat_id, lang, proc)

            if not connected:
                text = await tr_block(
                    lang,
                    f"❌ Gagal menautkan WhatsApp: {error_msg or 'kesalahan tidak diketahui'}.\n"
                    "Silakan ulangi dari menu.",
                )
                await bot.send_message(chat_id, text, buttons=await back_to_menu_kb(lang))
                return

            # Jeda kecil supaya file kredensial terakhir selesai ditulis ke disk.
            await asyncio.sleep(1)

            fmt = await _ask_format(conv, chat_id, lang)
            await _deliver_session(bot, chat_id, lang, session_dir, fmt)

    except asyncio.CancelledError:
        text = await tr_block(lang, "🛑 Proses dibatalkan.")
        await bot.send_message(chat_id, text)
        raise
    except asyncio.TimeoutError:
        text = await tr_block(lang, "⏰ Waktu habis, kamu tidak merespon. Silakan ulangi dari menu.")
        await bot.send_message(chat_id, text, buttons=await back_to_menu_kb(lang))
    except Exception as e:
        text = await tr_block(lang, "❌ Terjadi kesalahan tak terduga:")
        await bot.send_message(chat_id, f"{text}\n`{type(e).__name__}: {e}`", buttons=await back_to_menu_kb(lang))
    finally:
        if proc is not None and proc.returncode is None:
            proc.kill()
            try:
                await proc.wait()
            except Exception:
                pass
        # WAJIB: hapus folder sesi apa pun hasilnya -- file kredensial
        # WhatsApp setara password akun, tidak boleh nyangkut di disk.
        shutil.rmtree(session_dir, ignore_errors=True)


async def _watch_pairing(bot, chat_id, lang, proc):
    """Baca stdout proses Node baris demi baris sampai CONNECTED / ERROR
    / TIMEOUT, atau sampai PAIRING_TIMEOUT detik terlampaui."""
    connected = False
    error_msg = None

    try:
        async with asyncio.timeout(PAIRING_TIMEOUT):
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text_line = line.decode(errors="ignore").strip()
                if not text_line:
                    continue

                if text_line.startswith("PAIRING_CODE:"):
                    pairing_code = text_line.split(":", 1)[1]
                    msg = await tr_block(
                        lang,
                        "🔗 **Kode pairing WhatsApp kamu:**\n\n"
                        f"`{pairing_code}`\n\n"
                        "Buka WhatsApp di HP kamu:\n"
                        "**Setelan → Perangkat Tertaut → Tautkan dengan nomor telepon**\n"
                        "lalu masukkan kode di atas dalam 2 menit.",
                    )
                    await bot.send_message(chat_id, msg)

                elif text_line == "CONNECTED":
                    connected = True
                    break

                elif text_line.startswith("ERROR:"):
                    error_msg = text_line.split(":", 1)[1]
                    break

                elif text_line == "TIMEOUT":
                    error_msg = "Waktu pairing habis."
                    break
    except (asyncio.TimeoutError, TimeoutError):
        error_msg = error_msg or "Waktu pairing habis."

    return connected, error_msg


async def _ask(bot, conv, lang, text, buttons=None):
    # PENTING: harus lewat conv.send_message() (bukan bot.send_message()
    # langsung) -- lihat catatan yang sama di handlers/session_gen.py.
    translated = await tr_block(lang, text)
    btns = buttons if buttons is not None else await cancel_kb(lang)
    await conv.send_message(translated, buttons=btns)
    resp = await conv.get_response(timeout=CONVERSATION_TIMEOUT)
    if resp.raw_text.strip().lower() in CANCEL_WORDS:
        raise asyncio.CancelledError()
    return resp.raw_text.strip()


async def _ask_format(conv, chat_id, lang):
    """Tampilkan tombol pilihan format file, tunggu user KLIK salah
    satu (bukan ketik teks) -- pakai conv.wait_event() supaya tetap
    dalam scope percakapan yang sama."""
    zip_label, json_label = await tr_many(lang, ["📦 Multi File (ZIP)", "📄 Single File (JSON)"])
    await conv.send_message(
        await tr_block(lang, "✅ **WhatsApp berhasil ditautkan!**\n\nPilih format file session yang kamu mau:"),
        buttons=[[Button.inline(zip_label, data="wa:zip"), Button.inline(json_label, data="wa:json")]],
    )
    try:
        resp = await conv.wait_event(
            events.CallbackQuery(pattern=b"wa:(zip|json)", chats=chat_id),
            timeout=FORMAT_CHOICE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        # Default aman kalau user tidak pilih dalam waktu -> Multi File (ZIP).
        return "zip"
    await resp.answer()
    return resp.data.decode().split(":")[-1]


async def _deliver_session(bot, chat_id, lang, session_dir, fmt: str):
    if fmt == "json":
        combined = _combine_session_json(session_dir)
        out_path = os.path.join(session_dir, "_output_session.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2)
        caption = await tr_block(
            lang,
            "✅ **Session WhatsApp (Single JSON) berhasil dibuat!**\n\n"
            "⚠️ **JANGAN bagikan file ini ke siapa pun.** File ini "
            "setara dengan akses penuh ke akun WhatsApp kamu.",
        )
        await bot.send_file(chat_id, out_path, caption=caption, buttons=await back_to_menu_kb(lang))
    else:
        out_path = os.path.join(BASE_DIR, "data", "wa_sessions", f"{os.path.basename(session_dir)}.zip")
        _zip_session_dir(session_dir, out_path)
        caption = await tr_block(
            lang,
            "✅ **Session WhatsApp (Multi File ZIP) berhasil dibuat!**\n\n"
            "⚠️ **JANGAN bagikan file ini ke siapa pun.** File ini "
            "setara dengan akses penuh ke akun WhatsApp kamu.",
        )
        await bot.send_file(chat_id, out_path, caption=caption, buttons=await back_to_menu_kb(lang))
        try:
            os.remove(out_path)
        except OSError:
            pass


def _combine_session_json(session_dir: str) -> dict:
    """Gabungan semua file JSON hasil useMultiFileAuthState Baileys jadi
    SATU objek JSON: {"creds": {...}, "keys": {"<nama file>": {...}}}."""
    combined = {"creds": None, "keys": {}}
    for fname in os.listdir(session_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(session_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if fname == "creds.json":
            combined["creds"] = data
        else:
            combined["keys"][fname[:-5]] = data  # buang ".json"
    return combined


def _zip_session_dir(session_dir: str, out_path: str) -> None:
    """Zip struktur asli folder useMultiFileAuthState Baileys apa adanya
    (creds.json + banyak file kunci lain) -- ini format "Multi File"."""
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(session_dir):
            if fname.endswith(".json"):
                zf.write(os.path.join(session_dir, fname), arcname=fname)
