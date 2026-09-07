"""
handlers/admin.py
Panel kontrol admin lewat perintah /admin. Dari sini admin bisa mengatur
100% perilaku bot tanpa sentuh kode atau restart:

- Force Join: aktif/nonaktif, tambah/hapus channel atau grup wajib
- Fitur Generate: aktif/nonaktif Telethon & Pyrogram secara terpisah
- Edit Pesan: ubah teks welcome & about (atau reset ke default)
- Broadcast: kirim pesan ke semua user yang pernah /start
- Mode Maintenance: matikan sementara akses non-admin
- Kelola Admin: tambah/hapus admin tambahan (selain dari .env)

Semua perubahan disimpan lewat utils/settings (JSON live), jadi langsung
berlaku untuk request berikutnya tanpa perlu restart bot.
"""

import asyncio

from telethon import events

from config import CONVERSATION_TIMEOUT
from utils import settings, keyboards as kb

CANCEL_WORDS = {"/cancel", "batal", "cancel"}


def register(bot):
    @bot.on(events.NewMessage(pattern="/admin"))
    async def admin_cmd(event):
        if not settings.is_admin(event.sender_id):
            # Diam saja untuk non-admin, jangan bocorkan keberadaan /admin.
            return
        await event.respond(
            "🛠️ **Panel Admin**\n\nKelola semua pengaturan bot di sini.",
            buttons=kb.admin_main_kb(),
        )

    @bot.on(events.CallbackQuery(pattern=b"adm:"))
    async def admin_router(event):
        if not settings.is_admin(event.sender_id):
            await event.answer("⛔ Kamu bukan admin.", alert=True)
            return

        data = event.data.decode()

        if data == "adm:back":
            await event.edit("🛠️ **Panel Admin**", buttons=kb.admin_main_kb())

        elif data == "adm:close":
            await event.delete()

        elif data == "adm:stats":
            await event.edit(_stats_text(), buttons=kb.admin_main_kb())

        elif data == "adm:fj":
            await event.edit(_fj_text(), buttons=kb.admin_fj_kb())

        elif data == "adm:fj:toggle":
            settings.set_force_join_enabled(not settings.force_join_enabled())
            await event.edit(_fj_text(), buttons=kb.admin_fj_kb())

        elif data.startswith("adm:fjdel:"):
            idx = int(data.split(":")[-1])
            channels = settings.force_join_channels()
            if 0 <= idx < len(channels):
                settings.remove_force_join_channel(channels[idx]["username"])
                await event.answer("🗑️ Channel dihapus.")
            await event.edit(_fj_text(), buttons=kb.admin_fj_kb())

        elif data == "adm:fjadd":
            await event.answer()
            asyncio.create_task(_flow_add_channel(bot, event))

        elif data == "adm:feature":
            await event.edit(
                "🔧 **Fitur Generate**\n\nAktif/nonaktifkan library generate session:",
                buttons=kb.admin_feature_kb(),
            )

        elif data == "adm:feat:telethon":
            settings.set_feature("telethon_enabled", not settings.telethon_enabled())
            await event.edit("🔧 **Fitur Generate**", buttons=kb.admin_feature_kb())

        elif data == "adm:feat:pyrogram":
            settings.set_feature("pyrogram_enabled", not settings.pyrogram_enabled())
            await event.edit("🔧 **Fitur Generate**", buttons=kb.admin_feature_kb())

        elif data == "adm:msg":
            await event.edit("📝 **Edit Pesan Bot**", buttons=kb.admin_msg_kb())

        elif data == "adm:msgset:welcome":
            await event.answer()
            asyncio.create_task(_flow_edit_text(bot, event, "welcome"))

        elif data == "adm:msgset:about":
            await event.answer()
            asyncio.create_task(_flow_edit_text(bot, event, "about"))

        elif data == "adm:msgreset:welcome":
            settings.set_welcome_text(None)
            await event.answer("♻️ Pesan Welcome direset ke default.")

        elif data == "adm:msgreset:about":
            settings.set_about_text(None)
            await event.answer("♻️ Pesan About direset ke default.")

        elif data == "adm:maint:toggle":
            settings.set_maintenance_mode(not settings.maintenance_mode())
            await event.edit("🛠️ **Panel Admin**", buttons=kb.admin_main_kb())

        elif data == "adm:broadcast":
            await event.answer()
            asyncio.create_task(_flow_broadcast(bot, event))

        elif data == "adm:admins":
            await event.edit("👮 **Kelola Admin**", buttons=kb.admin_admins_kb())

        elif data == "adm:adminadd":
            await event.answer()
            asyncio.create_task(_flow_add_admin(bot, event))

        elif data.startswith("adm:admindel:"):
            uid = int(data.split(":")[-1])
            if settings.is_env_admin(uid):
                await event.answer("⛔ Admin ini didaftarkan lewat .env, hapus manual dari sana.", alert=True)
            else:
                settings.remove_admin(uid)
                await event.answer("🗑️ Admin dihapus.")
            await event.edit("👮 **Kelola Admin**", buttons=kb.admin_admins_kb())

        else:
            await event.answer()


def _fj_text() -> str:
    channels = settings.force_join_channels()
    status = "✅ Aktif" if settings.force_join_enabled() else "❌ Nonaktif"
    lines = [f"📢 **Force Join** — Status: {status}", ""]
    if channels:
        for c in channels:
            lines.append(f"• {c.get('label') or c['username']} — {c['url']}")
    else:
        lines.append("_Belum ada channel/grup yang diwajibkan._")
    lines.append("\nKlik nama channel untuk menghapusnya.")
    return "\n".join(lines)


def _stats_text() -> str:
    return (
        "📊 **Statistik Bot**\n\n"
        f"👥 Total user tercatat: `{len(settings.all_users())}`\n"
        f"📢 Channel force join: `{len(settings.force_join_channels())}` "
        f"({'aktif' if settings.force_join_enabled() else 'nonaktif'})\n"
        f"🔑 Telethon: {'✅ aktif' if settings.telethon_enabled() else '❌ nonaktif'}\n"
        f"🔑 Pyrogram: {'✅ aktif' if settings.pyrogram_enabled() else '❌ nonaktif'}\n"
        f"🛑 Maintenance: {'✅ aktif' if settings.maintenance_mode() else '❌ nonaktif'}\n"
        f"👮 Total admin: `{len(settings.list_admins())}`\n"
    )


# ---------------------------------------------------------------------
# FLOW BERBASIS PERCAKAPAN (dijalankan sebagai background task supaya
# tidak memblok bot melayani user lain selagi menunggu balasan admin)
# ---------------------------------------------------------------------
async def _flow_add_channel(bot, event):
    chat_id = event.chat_id
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            # Kirim lewat conv.send_message() (bukan bot.send_message())
            # supaya conv.get_response() tahu pesan mana yang ditunggu
            # balasannya. Lihat catatan sama di handlers/session_gen.py.
            await conv.send_message(
                "📢 Kirim **username atau link** channel/grup yang wajib di-join.\n"
                "Contoh: `@namachannel` atau `https://t.me/namachannel`\n\n"
                "Ketik /cancel untuk batal.",
            )
            resp = await conv.get_response()
            text = (resp.raw_text or "").strip()
            if text.lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, "🛑 Dibatalkan.")
                return

            username = (
                text.replace("https://t.me/", "")
                .replace("http://t.me/", "")
                .lstrip("@")
                .strip("/")
            )
            if not username:
                await bot.send_message(chat_id, "❌ Format tidak dikenali. Silakan ulangi dari menu Force Join.")
                return

            await conv.send_message(
                "🏷️ Kirim label/nama tampilan untuk channel ini "
                "(atau ketik `-` untuk pakai default).",
            )
            resp2 = await conv.get_response()
            label_text = (resp2.raw_text or "").strip()
            label = None if label_text == "-" else label_text

            url = f"https://t.me/{username}"
            settings.add_force_join_channel(username, url, label)
            await bot.send_message(
                chat_id,
                f"✅ `{username}` ditambahkan ke daftar force join.",
                buttons=kb.admin_fj_kb(),
            )
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏰ Waktu habis, silakan ulangi dari menu.")


async def _flow_edit_text(bot, event, kind: str):
    chat_id = event.chat_id
    label = "Welcome" if kind == "welcome" else "About"
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            await conv.send_message(
                f"✏️ Kirim teks baru untuk pesan **{label}** (mendukung Markdown).\n"
                "Tips: gunakan `{name}` di pesan Welcome untuk menyisipkan nama user.\n\n"
                "Ketik /cancel untuk batal.",
            )
            resp = await conv.get_response()
            text = resp.raw_text or ""
            if text.strip().lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, "🛑 Dibatalkan.")
                return

            if kind == "welcome":
                settings.set_welcome_text(text)
            else:
                settings.set_about_text(text)
            await bot.send_message(chat_id, f"✅ Pesan {label} berhasil diperbarui.")
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏰ Waktu habis, silakan ulangi dari menu.")


async def _flow_broadcast(bot, event):
    chat_id = event.chat_id
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            await conv.send_message(
                "📣 Kirim pesan teks yang ingin di-broadcast ke semua user bot.\n\n"
                "Ketik /cancel untuk batal.",
            )
            resp = await conv.get_response()
            text = resp.raw_text or ""
            if text.strip().lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, "🛑 Dibatalkan.")
                return
            if not text.strip():
                await bot.send_message(chat_id, "❌ Broadcast saat ini hanya mendukung pesan teks.")
                return

            users = settings.all_users()
            await bot.send_message(chat_id, f"⏳ Mengirim ke {len(users)} user terdaftar...")

            success, failed = 0, 0
            for uid in users:
                try:
                    await bot.send_message(uid, text, link_preview=False)
                    success += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.05)  # hindari flood limit Telegram

            await bot.send_message(
                chat_id,
                f"✅ Broadcast selesai.\nBerhasil: `{success}` | Gagal: `{failed}`",
            )
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏰ Waktu habis, silakan ulangi dari menu.")


async def _flow_add_admin(bot, event):
    chat_id = event.chat_id
    try:
        async with bot.conversation(chat_id, timeout=CONVERSATION_TIMEOUT) as conv:
            await conv.send_message(
                "👮 Kirim **user ID** Telegram (angka) yang ingin dijadikan admin.\n"
                "_Tips: user tersebut bisa cek ID-nya lewat bot seperti @userinfobot._\n\n"
                "Ketik /cancel untuk batal.",
            )
            resp = await conv.get_response()
            text = (resp.raw_text or "").strip()
            if text.lower() in CANCEL_WORDS:
                await bot.send_message(chat_id, "🛑 Dibatalkan.")
                return
            if not text.lstrip("-").isdigit():
                await bot.send_message(chat_id, "❌ ID harus berupa angka. Silakan ulangi dari menu.")
                return

            settings.add_admin(int(text))
            await bot.send_message(
                chat_id,
                f"✅ User `{text}` sekarang menjadi admin.",
                buttons=kb.admin_admins_kb(),
            )
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏰ Waktu habis, silakan ulangi dari menu.")
