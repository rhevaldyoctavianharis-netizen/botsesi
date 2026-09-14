"""
handlers/whatsapp_gen.py  (DIUBAH — satu pesan status yang di-edit terus,
bukan kirim banyak pesan baru, biar chat tidak spam)

Generate session WhatsApp Multi-Device pakai Baileys (Node.js),
dipanggil sebagai SUBPROCESS terpisah per user dari whatsapp/pair.js.

Alur (tombol WhatsApp ada di bawah tombol Telethon/Pyrogram, lihat
utils/keyboards.choose_library_kb):
1. User klik "🟢 WhatsApp" -> pilih format file (ZIP/JSON) -- pesan
   pilihan ini DIHAPUS begitu dipilih (lihat handlers/callbacks.py)
2. Bot tanya nomor WhatsApp -> begitu user balas, pesan pertanyaan itu
   DIHAPUS dan diganti SATU pesan status "⏳ Memproses..."
3. Pesan status yang SAMA di-EDIT beberapa kali seiring progres:
   "⏳ Memproses..." -> "🔗 Kode pairing: xxxxxx" -> "✅ Terkoneksi!"
   atau "❌ Gagal: <alasan>"
4. Kalau CONNECTED -> file dikirim sesuai format yang sudah dipilih di
   langkah 1
5. Folder sesi SELALU dihapus setelah selesai (berhasil/gagal/timeout/
   dibatalkan) -- file kredensial WhatsApp setara password akun.

PENTING SOAL TRANSLATE: isi file kredensial (JSON WhatsApp) TIDAK
PERNAH dilewatkan ke translate -- cuma teks penjelasan yang diterjemahkan.

PENTING SOAL CONCURRENCY: proses Node adalah subprocess PENDEK per
sesi, dijalankan lewat asyncio.create_subprocess_exec yang non-blocking
-- banyak user bisa generate WhatsApp session BERSAMAAN tanpa saling
ganggu.
"""

import asyncio
import json
import os
import shutil
import uuid
import zipfile

from config import CONVERSATION_TIMEOUT
from utils.keyboards import cancel_kb, back_to_menu_kb
from utils.i18n import tr_block

CANCEL_WORDS = {"/cancel", "batal", "cancel"}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHATSAPP_SCRIPT = os.path.join(BASE_DIR, "whatsapp", "pair.js")
SESSIONS_ROOT = os.path.join(BASE_DIR, "data", "wa_sessions")

PAIRING_TIMEOUT = 130  # detik -- sedikit di atas TIMEOUT_MS (120 detik) di pair.js


async def run_generate_whatsapp(bot, event, lang: str = "id", fmt: str = "zip"):
    """`fmt` sudah dipilih user SEBELUM fungsi ini dipanggil (lihat
    handlers/callbacks.py: wa_format_cb) -- nilainya "zip" atau "json"."""
    chat_id = event.chat_id
    os.makedirs(SESSIONS_ROOT, exist_ok=True)
    session_dir = os.path.join(SESSIONS_ROOT, f"{chat_id}_{uuid.uuid4().hex[:8]}")
    proc = None
    status_msg = None

    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            ask_text = await tr_block(
                lang,
                "📱 **Kirim nomor WhatsApp** yang mau ditautkan.\n"
                "Format: `+62812xxxxxxx` (pakai kode negara)\n\n"
                "Ketik /cancel untuk membatalkan.",
            )
            ask_msg = await conv.send_message(ask_text, buttons=await cancel_kb(lang))
            resp = await conv.get_response(timeout=CONVERSATION_TIMEOUT)
            phone = resp.raw_text.strip()

            # Hapus pertanyaan nomor begitu user membalas -- ganti satu
            # pesan status yang akan di-edit terus-menerus (anti-spam).
            try:
                await ask_msg.delete()
            except Exception:
                pass

            if phone.lower() in CANCEL_WORDS:
                raise asyncio.CancelledError()

            status_msg = await bot.send_message(chat_id, await tr_block(lang, "⏳ Memproses..."))

            os.makedirs(session_dir, exist_ok=True)
            proc = await asyncio.create_subprocess_exec(
                "node", WHATSAPP_SCRIPT, phone, session_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            connected, error_msg = await _watch_pairing(status_msg, lang, proc)

            if not connected:
                text = await tr_block(
                    lang,
                    f"❌ Gagal menautkan WhatsApp: {error_msg or 'kesalahan tidak diketahui'}.\n"
                    "Silakan ulangi dari menu.",
                )
                await status_msg.edit(text, buttons=await back_to_menu_kb(lang))
                return

            # Jeda kecil supaya file kredensial terakhir selesai ditulis ke disk.
            await asyncio.sleep(1)

            await _deliver_session(bot, chat_id, lang, session_dir, fmt, status_msg)

    except asyncio.CancelledError:
        text = await tr_block(lang, "🛑 Proses dibatalkan.")
        if status_msg is not None:
            try:
                await status_msg.edit(text)
            except Exception:
                await bot.send_message(chat_id, text)
        else:
            await bot.send_message(chat_id, text)
        raise
    except asyncio.TimeoutError:
        text = await tr_block(lang, "⏰ Waktu habis, kamu tidak merespon. Silakan ulangi dari menu.")
        await bot.send_message(chat_id, text, buttons=await back_to_menu_kb(lang))
    except Exception as e:
        text = await tr_block(lang, "❌ Terjadi kesalahan tak terduga:")
        full = f"{text}\n`{type(e).__name__}: {e}`"
        if status_msg is not None:
            try:
                await status_msg.edit(full, buttons=await back_to_menu_kb(lang))
            except Exception:
                await bot.send_message(chat_id, full, buttons=await back_to_menu_kb(lang))
        else:
            await bot.send_message(chat_id, full, buttons=await back_to_menu_kb(lang))
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


async def _watch_pairing(status_msg, lang, proc):
    """Baca stdout proses Node baris demi baris, EDIT status_msg yang
    sama seiring progres (bukan kirim pesan baru), sampai CONNECTED /
    ERROR / TIMEOUT, atau sampai PAIRING_TIMEOUT detik terlampaui."""
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
                        "lalu masukkan kode di atas secepatnya (berlaku singkat).",
                    )
                    await status_msg.edit(msg)

                elif text_line == "CONNECTED":
                    connected = True
                    await status_msg.edit(await tr_block(lang, "✅ **Terkoneksi!** Menyiapkan file session..."))
                    break

                elif text_line.startswith("ERROR:"):
                    error_msg = text_line.split(":", 1)[1]
                    break

                elif text_line == "TIMEOUT":
                    error_msg = "Waktu pairing habis."
                    break

                else:
                    # Baris log lain dari Baileys yang bukan bagian
                    # protokol komunikasi kita -- diabaikan.
                    continue
    except (asyncio.TimeoutError, TimeoutError):
        error_msg = error_msg or "Waktu pairing habis."

    return connected, error_msg


async def _deliver_session(bot, chat_id, lang, session_dir, fmt: str, status_msg):
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

    # File sudah terkirim sebagai pesan terpisah (attachment) -- hapus
    # pesan status "Terkoneksi..." supaya tidak nyangkut sebagai pesan
    # duplikat/basi.
    try:
        await status_msg.delete()
    except Exception:
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
