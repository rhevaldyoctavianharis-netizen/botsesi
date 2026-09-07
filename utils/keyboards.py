"""
utils/keyboards.py  (DIUBAH — sekarang async + auto-translate)
Kumpulan layout tombol (inline keyboard) untuk seluruh bot, termasuk
panel admin. Semua LABEL tombol yang berupa teks (bukan nama channel
milik admin / nama bahasa) sekarang diterjemahkan otomatis ke bahasa
pilihan user lewat utils/i18n.py (Google Translate + cache) — makanya
hampir semua fungsi di sini jadi `async def` dan menerima parameter
`lang` (kode bahasa, default "id").

PENTING: yang diterjemahkan HANYA teks LABEL yang tampil ke user. Nilai
`data=` (callback data / identifier tombol seperti "menu:generate",
"adm:fj", dst) TIDAK PERNAH ikut diterjemahkan — itu harus selalu tetap
dalam Bahasa Indonesia/Inggris supaya router callback di setiap handler
tetap konsisten apa pun bahasa yang dipilih user.
"""

from telethon import Button

from config import OWNER_USERNAME
from utils import settings
from utils.i18n import tr_many
from utils.languages import LANGUAGES


# =======================================================================
# USER-FACING
# =======================================================================
async def join_channel_kb(channels, lang: str = "id"):
    """Tombol wajib join untuk tiap channel/grup + tombol cek ulang."""
    (already_joined_label,) = await tr_many(lang, ["✅ Saya Sudah Join"])
    buttons = [
        [Button.url(f"📢 Join {c.get('label') or c['username']}", c["url"])]
        for c in channels
    ]
    buttons.append([Button.inline(already_joined_label, data="check_join")])
    return buttons


async def main_menu_kb(lang: str = "id", is_admin: bool = False):
    """Menu utama setelah user lolos verifikasi join. Tombol
    "🛠️ Dashboard Admin" HANYA muncul kalau `is_admin=True`."""
    labels = await tr_many(lang, [
        "🔑 Generate Session Now",
        "ℹ️ Tentang Bot",
        "🌐 Bahasa",
    ])
    gen, about, bahasa = labels
    rows = [
        [Button.inline(gen, data="menu:generate")],
        [Button.inline(about, data="menu:about"), Button.inline(bahasa, data="menu:lang")],
        [Button.url("👤 Owner", f"https://t.me/{OWNER_USERNAME}")],
    ]
    if is_admin:
        (admin_label,) = await tr_many(lang, ["🛠️ Dashboard Admin"])
        rows.append([Button.inline(admin_label, data="adm:back")])
    return rows


async def choose_library_kb(lang: str = "id"):
    """Pilihan library: Telethon / Pyrogram."""
    labels = await tr_many(lang, ["🟦 Telethon", "🟩 Pyrogram", "⬅️ Kembali"])
    telethon_label, pyrogram_label, back_label = labels
    return [
        [
            Button.inline(telethon_label, data="gen:telethon"),
            Button.inline(pyrogram_label, data="gen:pyrogram"),
        ],
        [Button.inline(back_label, data="menu:back")],
    ]


async def cancel_kb(lang: str = "id"):
    (label,) = await tr_many(lang, ["❌ Batalkan"])
    return [[Button.inline(label, data="gen:cancel")]]


async def back_to_menu_kb(lang: str = "id"):
    (label,) = await tr_many(lang, ["⬅️ Menu Utama"])
    return [[Button.inline(label, data="menu:back")]]


async def language_menu_kb(page: int = 0, per_page: int = 10, lang: str = "id"):
    """Keyboard pilihan bahasa dengan pagination (183 bahasa, 10/halaman).
    Nama bahasa sendiri (French, Spanish, dst) SENGAJA tidak diterjemahkan
    — dibiarkan dalam Bahasa Inggris sebagai nama baku universal."""
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

    prev_label, next_label, back_label = await tr_many(lang, ["⬅️ Prev", "Next ➡️", "⬅️ Menu Utama"])
    nav = []
    if page > 0:
        nav.append(Button.inline(prev_label, data=f"lang:page:{page - 1}"))
    nav.append(Button.inline(f"{page + 1}/{total_pages}", data="lang:noop"))
    if page < total_pages - 1:
        nav.append(Button.inline(next_label, data=f"lang:page:{page + 1}"))
    rows.append(nav)

    rows.append([Button.inline(back_label, data="menu:back")])
    return rows


# =======================================================================
# ADMIN PANEL
# =======================================================================
async def admin_main_kb(lang: str = "id"):
    maint_on = settings.maintenance_mode()
    maint_src = ("🟢 Matikan" if maint_on else "🛑 Aktifkan") + " Mode Maintenance"
    labels = await tr_many(lang, [
        "📊 Statistik", "📢 Force Join", "🔧 Fitur Generate", "📝 Edit Pesan",
        "📣 Broadcast", maint_src, "👮 Kelola Admin", "❌ Tutup",
    ])
    stats, fj, feat, msg, bc, maint, admins, close = labels
    return [
        [Button.inline(stats, data="adm:stats")],
        [Button.inline(fj, data="adm:fj")],
        [Button.inline(feat, data="adm:feature")],
        [Button.inline(msg, data="adm:msg")],
        [Button.inline(bc, data="adm:broadcast")],
        [Button.inline(maint, data="adm:maint:toggle")],
        [Button.inline(admins, data="adm:admins")],
        [Button.inline(close, data="adm:close")],
    ]


async def admin_fj_kb(lang: str = "id"):
    channels = settings.force_join_channels()
    enabled = settings.force_join_enabled()
    toggle_src = ("✅ Aktif" if enabled else "❌ Nonaktif") + " — klik untuk toggle"
    toggle_label, add_label, back_label = await tr_many(
        lang, [toggle_src, "➕ Tambah Channel/Grup", "⬅️ Kembali"]
    )
    rows = [[Button.inline(toggle_label, data="adm:fj:toggle")]]
    for i, c in enumerate(channels):
        # Nama channel/label ditulis admin sendiri -> TIDAK diterjemahkan.
        rows.append([Button.inline(f"🗑️ {c.get('label') or c['username']}", data=f"adm:fjdel:{i}")])
    rows.append([Button.inline(add_label, data="adm:fjadd")])
    rows.append([Button.inline(back_label, data="adm:back")])
    return rows


async def admin_feature_kb(lang: str = "id"):
    t = settings.telethon_enabled()
    p = settings.pyrogram_enabled()
    t_label, p_label, back_label = await tr_many(lang, [
        ("✅" if t else "❌") + " Telethon — klik untuk toggle",
        ("✅" if p else "❌") + " Pyrogram — klik untuk toggle",
        "⬅️ Kembali",
    ])
    return [
        [Button.inline(t_label, data="adm:feat:telethon")],
        [Button.inline(p_label, data="adm:feat:pyrogram")],
        [Button.inline(back_label, data="adm:back")],
    ]


async def admin_msg_kb(lang: str = "id"):
    labels = await tr_many(lang, [
        "✏️ Edit Welcome", "♻️ Reset Welcome ke Default",
        "✏️ Edit About", "♻️ Reset About ke Default", "⬅️ Kembali",
    ])
    edit_w, reset_w, edit_a, reset_a, back = labels
    return [
        [Button.inline(edit_w, data="adm:msgset:welcome")],
        [Button.inline(reset_w, data="adm:msgreset:welcome")],
        [Button.inline(edit_a, data="adm:msgset:about")],
        [Button.inline(reset_a, data="adm:msgreset:about")],
        [Button.inline(back, data="adm:back")],
    ]


async def admin_admins_kb(lang: str = "id"):
    add_label, back_label = await tr_many(lang, ["➕ Tambah Admin", "⬅️ Kembali"])
    rows = []
    for uid in settings.list_admins():
        tag = " (dari .env)" if settings.is_env_admin(uid) else ""
        rows.append([Button.inline(f"🗑️ {uid}{tag}", data=f"adm:admindel:{uid}")])
    rows.append([Button.inline(add_label, data="adm:adminadd")])
    rows.append([Button.inline(back_label, data="adm:back")])
    return rows
