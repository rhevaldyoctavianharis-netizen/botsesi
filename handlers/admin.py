"""
handlers/admin.py  (DIUBAH — dashboard ikut translate + broadcast multi-bahasa)
Panel kontrol admin lewat perintah /admin (atau tombol "🛠️ Dashboard
Admin" di menu utama untuk user yang terdaftar sebagai admin — lihat
handlers/start.py). Dari sini admin bisa mengatur 100% perilaku bot
tanpa sentuh kode atau restart:

- Force Join: aktif/nonaktif, tambah/hapus channel atau grup wajib
- Fitur Generate: aktif/nonaktif Telethon & Pyrogram secara terpisah
- Edit Pesan: ubah teks welcome & about (atau reset ke default)
- Broadcast: kirim pesan ke semua user (otomatis diterjemahkan ke
  bahasa MASING-MASING penerima, bukan cuma bahasa admin)
- Mode Maintenance: matikan sementara akses non-admin
- Kelola Admin: tambah/hapus admin tambahan (selain dari .env)

Semua perubahan disimpan lewat utils/settings (JSON live), jadi langsung
berlaku untuk request berikutnya tanpa perlu restart bot. Teks & tombol
dashboard ini sekarang ikut diterjemahkan ke bahasa pilihan admin yang
sedang membukanya (tiap admin bisa punya bahasa berbeda-beda).

CATATAN JUJUR: teks custom welcome/about yang admin masukkan lewat
"Edit Pesan" DIANGGAP berbahasa Indonesia untuk keperluan auto-translate
saat ditampilkan ke user (lihat handlers/start.py). Kalau admin menulis
teks custom dalam bahasa lain, hasil translate-nya ke bahasa user lain
bisa kurang akurat -- ini batasan wajar dari pendekatan auto-translate,
bukan bug.
"""

import asyncio

from telethon import events

from config import CONVERSATION_TIMEOUT
from utils import settings, keyboards as kb
from utils.i18n import tr_block

CANCEL_WORDS = {"/cancel", "batal", "cancel"}


def register(bot):
    @bot.on(events.NewMessage(pattern="/admin"))
    async def admin_cmd(event):
        if not settings.is_admin(event.sender_id):
            # Diam saja untuk non-admin, jangan bocorkan keberadaan /admin.
            return
        lang = settings.get_user_language(event.sender_id)
        text = await tr_block(lang, "🛠️ **Panel Admin**\n\nKelola semua pengaturan bot di sini.")
        await event.respond(text, buttons=await kb.admin_main_kb(lang))

    @bot.on(events.CallbackQuery(pattern=b"adm:"))
    async def admin_router(event):
        if not settings.is_admin(event.sender_id):
            await event.answer("⛔ Kamu bukan admin.", alert=True)
            return

        lang = settings.get_user_language(event.sender_id)
        data = event.data.decode()

        if data == "adm:back":
            text = await tr_block(lang, "🛠️ **Panel Admin**")
            await event.edit(text, buttons=await kb.admin_main_kb(lang))

        elif data == "adm:close":
            await event.delete()

        elif data == "adm:stats":
            await event.edit(await _stats_text(lang), buttons=await kb.admin_main_kb(lang))

        elif data == "adm:fj":
            await event.edit(await _fj_text(lang), buttons=await kb.admin_fj_kb(lang))

        elif data == "adm:fj:toggle":
            settings.set_force_join_enabled(not settings.force_join_enabled())
            await event.edit(await _fj_text(lang), buttons=await kb.admin_fj_kb(lang))

        elif data.startswith("adm:fjdel:"):
            idx = int(data.split(":")[-1])
            channels = settings.force_join_channels()
            if 0 <= idx < len(channels):
                settings.remove_force_join_channel(channels[idx]["username"])
                await event.answer(await tr_block(lang, "🗑️ Channel dihapus."))
            await event.edit(await _fj_text(lang), buttons=await kb.admin_fj_kb(lang))

        elif data == "adm:fjadd":
            await event.answer()
            asyncio.create_task(_flow_add_channel(bot, event, lang))

        elif data == "adm:feature":
            text = await tr_block(lang, "🔧 **Fitur Generate**\n\nAktif/nonaktifkan library generate session:")
            await event.edit(text, buttons=await kb.admin_feature_kb(lang))

        elif data == "adm:feat:telethon":
            settings.set_feature("telethon_enabled", not settings.telethon_enabled())
            await event.edit(await tr_block(lang, "🔧 **Fitur Generate**"), buttons=await kb.admin_feature_kb(lang))

        elif data == "adm:feat:pyrogram":
            settings.set_feature("pyrogram_enabled", not settings.pyrogram_enabled())
            await event.edit(await tr_block(lang, "🔧 **Fitur Generate**"), buttons=await kb.admin_feature_kb(lang))

        elif data == "adm:msg":
            await event.edit(await tr_block(lang, "📝 **Edit Pesan Bot**"), buttons=await kb.admin_msg_kb(lang))

        elif data == "adm:msgset:welcome":
            await event.answer()
            asyncio.create_task(_flow_edit_text(bot, event, "welcome", lang))

        elif data == "adm:msgset:about":
            await event.answer()
            asyncio.create_task(_flow_edit_text(bot, event, "about", lang))

        elif data == "adm:msgreset:welcome":
            settings.set_welcome_text(None)
            await event.answer(await tr_block(lang, "♻️ Pesan Welcome direset ke default."))

        elif data == "adm:msgreset:about":
            settings.set_about_text(None)
            await event.answer(await tr_block(lang, "♻️ Pesan About direset ke default."))

        elif data == "adm:maint:toggle":
            settings.set_maintenance_mode(not settings.maintenance_mode())
            await event.edit(await tr_block(lang, "🛠️ **Panel Admin**"), buttons=await kb.admin_main_kb(lang))

        elif data == "adm:broadcast":
            await event.answer()
            asyncio.create_task(_flow_broadcast(bot, event, lang))

        elif data == "adm:admins":
            await event.edit(await tr_block(lang, "👮 **Kelola Admin**"), buttons=await kb.admin_admins_kb(lang))

        elif data == "adm:adminadd":
            await event.answer()
            asyncio.create_task(_flow_add_admin(bot, event, lang))

        elif data.startswith("adm:admindel:"):
            uid = int(data.split(":")[-1])
            if settings.is_env_admin(uid):
                await event.answer(
                    await tr_block(lang, "⛔ Admin ini didaftarkan lewat .env, hapus manual dari sana."),
                    alert=True,
                )
            else:
                settings.remove_admin(uid)
                await event.answer(await tr_block(lang, "🗑️ Admin dihapus."))
            await event.edit(await tr_block(lang, "👮 **Kelola Admin**"), buttons=await kb.admin_admins_kb(lang))

        else:
            await event.answer()


async def _fj_text(lang: str) -> str:
    channels = settings.force_join_channels()
    status = "✅ Aktif" if settings.force_join_enabled() else "❌ Nonaktif"
    header = await tr_block(lang, f"📢 **Force Join** — Status: {status}")
    lines = [header, ""]
    if channels:
        # Nama/label channel ditulis admin sendiri -> TIDAK diterjemahkan.
        for c in channels:
            lines.append(f"• {c.get('label') or c['username']} — {c['url']}")
    else:
        lines.append(await tr_block(lang, "_Belum ada channel/grup yang diwajibkan._"))
    lines.append(await tr_block(lang, "Klik nama channel untuk menghapusnya."))
    return "\n".join(lines)


async def _stats_text(lang: str) -> str:
    title = await tr_block(lang, "📊 **Statistik Bot**")
    labels_src = (
        "👥 Total user tercatat\n"
        "📢 Channel force join\n"
        "🔑 Telethon\n"
        "🔑 Pyrogram\n"
        "🛑 Maintenance\n"
        "👮 Total admin"
    )
    # tr_block menerjemahkan PER BARIS dan mengembalikan urutan yang sama
    # persis dengan input, jadi index di bawah aman dipakai.
    label_lines = (await tr_block(lang, labels_src)).split("\n")

    fj_status = "aktif" if settings.force_join_enabled() else "nonaktif"
    t_status = "✅" if settings.telethon_enabled() else "❌"
    p_status = "✅" if settings.pyrogram_enabled() else "❌"
    m_status = "✅" if settings.maintenance_mode() else "❌"

    return (
        f"{title}\n\n"
        f"{label_lines[0]}: `{len(settings.all_users())}`\n"
        f"{label_lines[1]}: `{len(settings.force_join_channels())}` ({fj_status})\n"
        f"{label_lines[2]}: {t_status}\n"
        f"{label_lines[3]}: {p_status}\n"
        f"{label_lines[4]}: {m_status}\n"
        f"{label_lines[5]}: `{len(settings.list_admins())}`\n"
    )


# ---------------------------------------------------------------------
# FLOW BERBASIS PERCAKAPAN (dijalankan sebagai background task supaya
# tidak memblok bot melayani user lain selagi menunggu balasan admin)
# ---------------------------------------------------------------------
async def _flow_add_channel(bot, event, lang: str):
    chat_id = event.chat_id
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            prompt = await tr_block(
                lang,
                "📢 Kirim **username atau link** channel/grup yang wajib di-join.\n"
                "Contoh: `@namachannel` atau `https://t.me/namachannel`\n\n"
                "Ketik /cancel untuk batal.",
            )
            await conv.send_message(prompt)
            resp = await conv.get_response()
            text = (resp.raw_text or "").strip()
            if text.lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, await tr_block(lang, "🛑 Dibatalkan."))
                return

            username = (
                text.replace("https://t.me/", "")
                .replace("http://t.me/", "")
                .lstrip("@")
                .strip("/")
            )
            if not username:
                await bot.send_message(chat_id, await tr_block(lang, "❌ Format tidak dikenali. Silakan ulangi dari menu Force Join."))
                return

            label_prompt = await tr_block(
                lang,
                "🏷️ Kirim label/nama tampilan untuk channel ini "
                "(atau ketik `-` untuk pakai default).",
            )
            await conv.send_message(label_prompt)
            resp2 = await conv.get_response()
            label_text = (resp2.raw_text or "").strip()
            label = None if label_text == "-" else label_text

            url = f"https://t.me/{username}"
            settings.add_force_join_channel(username, url, label)
            success = await tr_block(lang, "✅ Channel berhasil ditambahkan ke daftar force join:")
            await bot.send_message(chat_id, f"{success}\n`{username}`", buttons=await kb.admin_fj_kb(lang))
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, await tr_block(lang, "⏰ Waktu habis, silakan ulangi dari menu."))


async def _flow_edit_text(bot, event, kind: str, lang: str):
    chat_id = event.chat_id
    label_src = "Welcome" if kind == "welcome" else "About"
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            prompt = await tr_block(
                lang,
                f"✏️ Kirim teks baru untuk pesan **{label_src}** (mendukung Markdown).\n"
                "Tips: gunakan `{name}` di pesan Welcome untuk menyisipkan nama user.\n\n"
                "Ketik /cancel untuk batal.",
            )
            await conv.send_message(prompt)
            resp = await conv.get_response()
            text = resp.raw_text or ""
            if text.strip().lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, await tr_block(lang, "🛑 Dibatalkan."))
                return

            # PENTING: teks yang admin masukkan di sini DISIMPAN APA ADANYA
            # (tidak ikut ditranslate sekarang) -- ini jadi SUMBER baru yang
            # otomatis diterjemahkan ke bahasa tiap user saat welcome/about
            # ditampilkan (lihat handlers/start.py & catatan di atas file ini).
            if kind == "welcome":
                settings.set_welcome_text(text)
            else:
                settings.set_about_text(text)
            done = await tr_block(lang, f"✅ Pesan {label_src} berhasil diperbarui.")
            await bot.send_message(chat_id, done)
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, await tr_block(lang, "⏰ Waktu habis, silakan ulangi dari menu."))


async def _flow_broadcast(bot, event, lang: str):
    chat_id = event.chat_id
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            prompt = await tr_block(
                lang,
                "📣 Kirim pesan teks yang ingin di-broadcast ke semua user bot.\n\n"
                "Ketik /cancel untuk batal.",
            )
            await conv.send_message(prompt)
            resp = await conv.get_response()
            text = resp.raw_text or ""
            if text.strip().lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, await tr_block(lang, "🛑 Dibatalkan."))
                return
            if not text.strip():
                await bot.send_message(chat_id, await tr_block(lang, "❌ Broadcast saat ini hanya mendukung pesan teks."))
                return

            users = settings.all_users()
            sending = await tr_block(lang, "⏳ Mengirim ke")
            to_users = await tr_block(lang, "user terdaftar...")
            await bot.send_message(chat_id, f"{sending} {len(users)} {to_users}")

            success, failed = 0, 0
            for uid in users:
                # Broadcast diterjemahkan otomatis ke bahasa MASING-MASING
                # user penerima (bukan cuma bahasa admin pengirim).
                target_lang = settings.get_user_language(uid)
                translated_msg = await tr_block(target_lang, text)
                try:
                    await bot.send_message(uid, translated_msg, link_preview=False)
                    success += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.05)  # hindari flood limit Telegram

            result = await tr_block(lang, "✅ Broadcast selesai.\nBerhasil")
            failed_label = await tr_block(lang, "Gagal")
            await bot.send_message(chat_id, f"{result}: `{success}` | {failed_label}: `{failed}`")
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, await tr_block(lang, "⏰ Waktu habis, silakan ulangi dari menu."))


async def _flow_add_admin(bot, event, lang: str):
    chat_id = event.chat_id
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            prompt = await tr_block(
                lang,
                "👮 Kirim **user ID** Telegram (angka) yang ingin dijadikan admin.\n"
                "_Tips: user tersebut bisa cek ID-nya lewat bot seperti @userinfobot._\n\n"
                "Ketik /cancel untuk batal.",
            )
            await conv.send_message(prompt)
            resp = await conv.get_response()
            text = (resp.raw_text or "").strip()
            if text.lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, await tr_block(lang, "🛑 Dibatalkan."))
                return
            if not text.lstrip("-").isdigit():
                await bot.send_message(chat_id, await tr_block(lang, "❌ ID harus berupa angka. Silakan ulangi dari menu."))
                return

            settings.add_admin(int(text))
            confirm = await tr_block(lang, "✅ User berikut sekarang menjadi admin:")
            await bot.send_message(chat_id, f"{confirm}\n`{text}`", buttons=await kb.admin_admins_kb(lang))
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, await tr_block(lang, "⏰ Waktu habis, silakan ulangi dari menu."))
