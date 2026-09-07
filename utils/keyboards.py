"""
utils/keyboards.py
Kumpulan layout tombol (inline keyboard) yang dipakai di seluruh bot,
termasuk panel admin. Dipisah biar desain menu gampang diubah tanpa
nyentuh logic handler.
"""

from telethon import Button
from config import OWNER_USERNAME
from utils import settings
from utils.languages import LANGUAGES


# =======================================================================
# USER-FACING
# =======================================================================
def join_channel_kb(channels):
    """Tombol wajib join untuk setiap channel yang belum di-join + tombol cek ulang."""
    buttons = [
        [Button.url(f"📢 Join {c.get('label') or c['username']}", c["url"])]
        for c in channels
    ]
    buttons.append([Button.inline("✅ Saya Sudah Join", data="check_join")])
    return buttons


def main_menu_kb():
    """Menu utama setelah user lolos verifikasi join."""
    return [
        [Button.inline("🔑 Generate Session Now", data="menu:generate")],
        [
            Button.inline("ℹ️ Tentang Bot", data="menu:about"),
            Button.inline("🌐 Bahasa", data="menu:lang"),
        ],
        [Button.url("👤 Owner", f"https://t.me/{OWNER_USERNAME}")],
    ]


def choose_library_kb():
    """Pilihan library: Telethon / Pyrogram."""
    return [
        [
            Button.inline("🟦 Telethon", data="gen:telethon"),
            Button.inline("🟩 Pyrogram", data="gen:pyrogram"),
        ],
        [Button.inline("⬅️ Kembali", data="menu:back")],
    ]


def cancel_kb():
    return [[Button.inline("❌ Batalkan", data="gen:cancel")]]


def back_to_menu_kb():
    return [[Button.inline("⬅️ Menu Utama", data="menu:back")]]


def language_menu_kb(page: int = 0, per_page: int = 10):
    """Keyboard pilihan bahasa dengan pagination (±180 bahasa, 10/halaman)."""
    total_pages = (len(LANGUAGES) - 1) // per_page + 1
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = LANGUAGES[start:start + per_page]

    rows = []
    for i in range(0, len(chunk), 2):
        row = [
            Button.inline(name, data=f"lang:set:{code}")
            for code, name in chunk[i:i + 2]
        ]
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(Button.inline("⬅️ Prev", data=f"lang:page:{page - 1}"))
    nav.append(Button.inline(f"{page + 1}/{total_pages}", data="lang:noop"))
    if page < total_pages - 1:
        nav.append(Button.inline("Next ➡️", data=f"lang:page:{page + 1}"))
    rows.append(nav)

    rows.append([Button.inline("⬅️ Menu Utama", data="menu:back")])
    return rows


# =======================================================================
# ADMIN PANEL
# =======================================================================
def admin_main_kb():
    maint_on = settings.maintenance_mode()
    return [
        [Button.inline("📊 Statistik", data="adm:stats")],
        [Button.inline("📢 Force Join", data="adm:fj")],
        [Button.inline("🔧 Fitur Generate", data="adm:feature")],
        [Button.inline("📝 Edit Pesan", data="adm:msg")],
        [Button.inline("📣 Broadcast", data="adm:broadcast")],
        [Button.inline(
            ("🟢 Matikan" if maint_on else "🛑 Aktifkan") + " Mode Maintenance",
            data="adm:maint:toggle",
        )],
        [Button.inline("👮 Kelola Admin", data="adm:admins")],
        [Button.inline("❌ Tutup", data="adm:close")],
    ]


def admin_fj_kb():
    channels = settings.force_join_channels()
    enabled = settings.force_join_enabled()
    rows = [[Button.inline(
        ("✅ Aktif" if enabled else "❌ Nonaktif") + " — klik untuk toggle",
        data="adm:fj:toggle",
    )]]
    for i, c in enumerate(channels):
        rows.append([Button.inline(f"🗑️ {c.get('label') or c['username']}", data=f"adm:fjdel:{i}")])
    rows.append([Button.inline("➕ Tambah Channel/Grup", data="adm:fjadd")])
    rows.append([Button.inline("⬅️ Kembali", data="adm:back")])
    return rows


def admin_feature_kb():
    t = settings.telethon_enabled()
    p = settings.pyrogram_enabled()
    return [
        [Button.inline(("✅" if t else "❌") + " Telethon — klik untuk toggle", data="adm:feat:telethon")],
        [Button.inline(("✅" if p else "❌") + " Pyrogram — klik untuk toggle", data="adm:feat:pyrogram")],
        [Button.inline("⬅️ Kembali", data="adm:back")],
    ]


def admin_msg_kb():
    return [
        [Button.inline("✏️ Edit Welcome", data="adm:msgset:welcome")],
        [Button.inline("♻️ Reset Welcome ke Default", data="adm:msgreset:welcome")],
        [Button.inline("✏️ Edit About", data="adm:msgset:about")],
        [Button.inline("♻️ Reset About ke Default", data="adm:msgreset:about")],
        [Button.inline("⬅️ Kembali", data="adm:back")],
    ]


def admin_admins_kb():
    rows = []
    for uid in settings.list_admins():
        tag = " (dari .env)" if settings.is_env_admin(uid) else ""
        rows.append([Button.inline(f"🗑️ {uid}{tag}", data=f"adm:admindel:{uid}")])
    rows.append([Button.inline("➕ Tambah Admin", data="adm:adminadd")])
    rows.append([Button.inline("⬅️ Kembali", data="adm:back")])
    return rows
