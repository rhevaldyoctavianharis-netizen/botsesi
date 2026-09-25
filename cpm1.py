import asyncio
import csv
import io
import json
import random
import string
import sqlite3
import requests
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIG ====================
API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = "8408159368:AAHb9HPJapiC5qW1k4b2O1gW1osXFJGondY"

ADMIN_IDS = set(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())

NEW_USER_COINS = 5
COIN_PER_INJECT = 1
SPONSOR_REWARD = 2
REFERRAL_REWARD = 1
INJECT_COOLDOWN = 60
MAX_INJECT_PER_DAY = 20

DEFAULT_SETTINGS = {
    "sponsor_channel": "@sponsorchannel",
    "sponsor_link": "https://t.me/sponsorchannel",
    "admin_contact": "@adminusername",
    "thumbnail_url": "https://i.imgur.com/8Q0yqXx.jpg",
    "maintenance": "0",
    "force_join": "1",
}

FIREBASE_API_KEY = 'AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM'
FIREBASE_LOGIN_URL = (
    f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword"
    f"?key={FIREBASE_API_KEY}"
)
RANK_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/SetUserRating6"
REAL_ESTATE_VALUE = 10


# ==================== DATABASE ====================
DB = "cpmbot.db"


def db_exec(query, params=()):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()


def db_fetch(query, params=()):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, params)
    row = c.fetchone()
    conn.close()
    return row


def db_fetchall(query, params=()):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows


def init_db():
    db_exec("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        coins INTEGER DEFAULT 5,
        banned INTEGER DEFAULT 0,
        total_inject INTEGER DEFAULT 0,
        sponsor_claimed INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        last_daily TEXT,
        last_inject TEXT,
        today_inject INTEGER DEFAULT 0,
        today_date TEXT,
        note TEXT,
        joined_at TEXT
    )""")
    db_exec("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    db_exec("""CREATE TABLE IF NOT EXISTS inject_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT,
        status TEXT,
        timestamp TEXT
    )""")
    db_exec("""CREATE TABLE IF NOT EXISTS topup_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        price TEXT,
        proof TEXT,
        status TEXT DEFAULT 'pending',
        timestamp TEXT
    )""")
    db_exec("""CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        target TEXT,
        timestamp TEXT
    )""")
    for k, v in DEFAULT_SETTINGS.items():
        db_exec("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, str(v)))


def gen_ref_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_user(uid):
    return db_fetch("SELECT * FROM users WHERE user_id=?", (uid,))


def ensure_user(uid, username, referred_by=None):
    if get_user(uid):
        return
    code = gen_ref_code()
    while db_fetch("SELECT 1 FROM users WHERE referral_code=?", (code,)):
        code = gen_ref_code()
    db_exec(
        "INSERT INTO users (user_id, username, coins, banned, total_inject, "
        "sponsor_claimed, referral_code, referred_by, referral_count, "
        "daily_streak, today_inject, joined_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid, username or "", NEW_USER_COINS, 0, 0, 0, code, referred_by, 0, 0, 0,
         datetime.now().isoformat()),
    )
    if referred_by and get_user(referred_by):
        ref = get_user(referred_by)
        db_exec("UPDATE users SET coins=?, referral_count=? WHERE user_id=?",
                (ref[2] + REFERRAL_REWARD, ref[8] + 1, referred_by))


def update_user(uid, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    db_exec(f"UPDATE users SET {sets} WHERE user_id=?", (*kwargs.values(), uid))


def get_setting(key):
    row = db_fetch("SELECT value FROM settings WHERE key=?", (key,))
    return row[0] if row else DEFAULT_SETTINGS.get(key, "")


def set_setting(key, value):
    db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))


def log_admin(admin_id, action, target=""):
    db_exec("INSERT INTO admin_logs (admin_id, action, target, timestamp) VALUES (?,?,?,?)",
            (admin_id, action, target, datetime.now().isoformat()))


def add_inject_history(uid, email, status):
    db_exec("INSERT INTO inject_history (user_id, email, status, timestamp) VALUES (?,?,?,?)",
            (uid, email, status, datetime.now().isoformat()))


# ==================== CPM LOGIC ====================
def cpm_login(email, password):
    payload = {
        "clientType": "CLIENT_TYPE_ANDROID",
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12)",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(FIREBASE_LOGIN_URL, headers=headers, json=payload, timeout=15)
        d = r.json()
        if r.status_code == 200 and "idToken" in d:
            return d["idToken"], None
        return None, d.get("error", {}).get("message", "Unknown error")
    except Exception as e:
        return None, str(e)


def cpm_set_rank(token, real_estate_value=REAL_ESTATE_VALUE):
    rating_data = {
        k: 100000
        for k in [
            "cars", "car_fix", "car_collided", "car_exchange", "car_trade", "car_wash",
            "slicer_cut", "drift_max", "drift", "cargo", "delivery", "taxi", "levels", "gifts",
            "fuel", "offroad", "speed_banner", "reactions", "police", "run",
            "t_distance", "treasure", "block_post", "push_ups", "burnt_tire", "passanger_distance",
        ]
    }
    rating_data["time"] = 10000000000
    rating_data["race_win"] = 3000
    rating_data["real_estate"] = real_estate_value

    payload = {"data": json.dumps({"RatingData": rating_data})}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "okhttp/3.12.13",
    }
    try:
        r = requests.post(RANK_URL, headers=headers, json=payload, timeout=15)
        return r.status_code == 200, r.text[:200]
    except Exception as e:
        return False, str(e)


# ==================== STATE ====================
user_states = {}
admin_states = {}


# ==================== HELPERS ====================
def is_admin(uid):
    return uid in ADMIN_IDS


def is_banned(uid):
    u = get_user(uid)
    return u and u[3] == 1 and not is_admin(uid)


async def is_joined(uid):
    try:
        await client(GetParticipantRequest(
            channel=get_setting("sponsor_channel"), participant=uid))
        return True
    except Exception:
        return False


def can_inject(uid):
    u = get_user(uid)
    today = datetime.now().strftime("%Y-%m-%d")
    if u[12] != today:
        update_user(uid, today_inject=0, today_date=today)
        u = get_user(uid)
    if u[11] >= MAX_INJECT_PER_DAY:
        return False, f"Limit harian tercapai ({MAX_INJECT_PER_DAY}/hari)."
    if u[10]:
        try:
            last = datetime.fromisoformat(u[10])
            diff = (datetime.now() - last).total_seconds()
            if diff < INJECT_COOLDOWN:
                return False, f"Tunggu {int(INJECT_COOLDOWN - diff)}s lagi."
        except Exception:
            pass
    return True, ""


# ==================== UI BUILDERS ====================
def main_menu_buttons(is_admin=False):
    buttons = [
        [Button.inline("🎮 ɪɴᴊᴇᴄᴛ ʀᴀɴᴋ", b"menu_inject"),
         Button.inline("📊 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", b"menu_leaderboard")],
        [Button.inline("👤 ᴘʀᴏꜰɪʟᴇ", b"menu_profile"),
         Button.inline("📜 ʜɪꜱᴛᴏʀʏ", b"menu_history")],
        [Button.inline("💰 ᴛᴏᴘ-ᴜᴘ", b"menu_topup"),
         Button.inline("👥 ʀᴇꜰᴇʀʀᴀʟ", b"menu_referral")],
        [Button.inline("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", b"menu_join"),
         Button.inline("❓ ʜᴇʟᴘ", b"menu_help")],
    ]
    if is_admin:
        buttons.append([Button.inline("🛡️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", b"admin_panel")])
    return buttons


def back_button(target=b"menu_main"):
    return [[Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", target)]]


def build_main_caption(uid):
    u = get_user(uid)
    return (
        f"👑 **ᴄᴘᴍ ᴋɪɴɢ ʀᴀɴᴋ ʙᴏᴛ** 👑\n\n"
        f"👋 Halo, {u[1] or 'User'}!\n\n"
        f"💰 Coin: **{u[2]}**\n"
        f"🎯 Total Inject: **{u[4]}**\n"
        f"👥 Referral: **{u[8]}**\n\n"
        f"🎯 1 inject = {COIN_PER_INJECT} coin\n"
        f"🎁 User baru dapat {NEW_USER_COINS} coin gratis"
    )


def admin_panel_buttons():
    return [
        [Button.inline("📊 ꜱᴛᴀᴛꜱ", b"admin_stats"),
         Button.inline("👥 ᴜꜱᴇʀꜱ", b"admin_users_0")],
        [Button.inline("💰 ᴛᴏᴘᴜᴘ ʀᴇǫ", b"admin_topup_0")],
        [Button.inline("🚫 ʙᴀɴ", b"admin_ban"),
         Button.inline("✅ ᴜɴʙᴀɴ", b"admin_unban")],
        [Button.inline("➕ ᴄᴏɪɴ", b"admin_addcoin"),
         Button.inline("➖ ᴄᴏɪɴ", b"admin_remcoin")],
        [Button.inline("📝 ɴᴏᴛᴇ", b"admin_note"),
         Button.inline("📜 ʟᴏɢ", b"admin_logs_0")],
        [Button.inline("📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", b"admin_broadcast")],
        [Button.inline("📤 ᴇxᴘᴏʀᴛ ᴄꜱᴠ", b"admin_export")],
        [Button.inline("⚙️ ꜱᴇᴛᴛɪɴɢꜱ", b"admin_settings")],
        [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"menu_main")],
    ]


def settings_buttons():
    return [
        [Button.inline("📢 ꜱᴇᴛ ᴄʜᴀɴɴᴇʟ", b"admin_set_sponsor")],
        [Button.inline("🔗 ꜱᴇᴛ ʟɪɴᴋ", b"admin_set_link")],
        [Button.inline("👤 ꜱᴇᴛ ᴀᴅᴍɪɴ ᴄᴏɴᴛᴀᴄᴛ", b"admin_set_contact")],
        [Button.inline("🖼️ ꜱᴇᴛ ᴛʜᴜᴍʙɴᴀɪʟ", b"admin_set_thumb")],
        [Button.inline("🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ", b"admin_toggle_maint")],
        [Button.inline("🔒 ꜰᴏʀᴄᴇ ᴊᴏɪɴ", b"admin_toggle_join")],
        [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"admin_panel")],
    ]


# ==================== CLIENT ====================
client = TelegramClient("cpmbot_session", API_ID, API_HASH)
client.flood_sleep_threshold = 60


async def edit_menu(chat_id, msg_id, caption, buttons):
    try:
        await client.edit_message(chat_id, msg_id, caption, buttons=buttons)
        return msg_id
    except Exception:
        try:
            await client.delete_messages(chat_id, msg_id)
        except Exception:
            pass
        try:
            m = await client.send_file(chat_id, get_setting("thumbnail_url"),
                                       caption=caption, buttons=buttons)
        except Exception:
            m = await client.send_message(chat_id, caption, buttons=buttons)
        return m.id


async def send_main_menu(chat_id, uid, delete_msg_id=None):
    if delete_msg_id:
        try:
            await client.delete_messages(chat_id, delete_msg_id)
        except Exception:
            pass
    try:
        m = await client.send_file(chat_id, get_setting("thumbnail_url"),
                                   caption=build_main_caption(uid),
                                   buttons=main_menu_buttons(is_admin(uid)))
    except Exception:
        m = await client.send_message(chat_id, build_main_caption(uid),
                                      buttons=main_menu_buttons(is_admin(uid)))
    user_states.setdefault(uid, {})["menu_msg"] = m.id
    user_states[uid]["state"] = "main"
    return m.id


def get_menu_msg(uid):
    return user_states.get(uid, {}).get("menu_msg")


# ==================== START ====================
@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(event):
    uid = event.sender_id
    username = event.sender.username or event.sender.first_name or ""

    args = event.text.split()
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            code = args[1][4:]
            ref_row = db_fetch("SELECT user_id FROM users WHERE referral_code=?", (code,))
            if ref_row and ref_row[0] != uid:
                referred_by = ref_row[0]
        except Exception:
            pass

    ensure_user(uid, username, referred_by)

    try:
        await event.delete()
    except Exception:
        pass

    if is_banned(uid):
        try:
            await event.respond("🚫 Anda diblokir dari bot ini.")
        except Exception:
            pass
        return

    if get_setting("maintenance") == "1" and not is_admin(uid):
        try:
            await event.respond("🔧 **Bot sedang maintenance.**\n\nCoba lagi nanti.")
        except Exception:
            pass
        return

    if get_setting("force_join") == "1" and not is_admin(uid):
        if not await is_joined(uid):
            buttons = [
                [Button.url("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", get_setting("sponsor_link"))],
                [Button.inline("✅ ꜱᴜᴅᴀʜ ᴊᴏɪɴ", b"check_join")],
            ]
            try:
                await client.send_file(
                    event.chat_id, get_setting("thumbnail_url"),
                    caption="🔒 **Anda harus join channel sponsor dulu** untuk pakai bot.",
                    buttons=buttons)
            except Exception:
                await event.respond("🔒 Join channel sponsor dulu.", buttons=buttons)
            return

    old = get_menu_msg(uid)
    if old:
        try:
            await client.delete_messages(event.chat_id, old)
        except Exception:
            pass

    await send_main_menu(event.chat_id, uid)


@client.on(events.NewMessage(pattern="/cancel"))
async def cmd_cancel(event):
    uid = event.sender_id
    try:
        await event.delete()
    except Exception:
        pass
    if uid in user_states:
        user_states[uid]["state"] = "main"
    if uid in admin_states:
        admin_states.pop(uid, None)
    menu_msg = get_menu_msg(uid)
    if menu_msg:
        await edit_menu(event.chat_id, menu_msg, build_main_caption(uid),
                        main_menu_buttons(is_admin(uid)))


# ==================== CALLBACK ====================
@client.on(events.CallbackQuery())
async def callback_handler(event):
    uid = event.sender_id
    data = event.data.decode() if isinstance(event.data, bytes) else event.data

    if is_banned(uid):
        await event.answer("🚫 Anda diblokir.", alert=True)
        return

    user = get_user(uid)
    if not user:
        ensure_user(uid, "")
        user = get_user(uid)

    await event.answer()

    if data == "check_join":
        if await is_joined(uid):
            await event.delete()
            await send_main_menu(event.chat_id, uid)
        else:
            await event.answer("❌ Belum join channel.", alert=True)
        return

    menu_msg = get_menu_msg(uid)
    if not menu_msg:
        menu_msg = await send_main_menu(event.chat_id, uid)

    if data.startswith("menu_") or data == "admin_panel":
        if uid in user_states:
            user_states[uid]["state"] = "main"

    # ==================== MENU ====================
    if data == "menu_main":
        await edit_menu(event.chat_id, menu_msg, build_main_caption(uid),
                        main_menu_buttons(is_admin(uid)))

    elif data == "menu_inject":
        if user[2] < COIN_PER_INJECT:
            await edit_menu(event.chat_id, menu_msg,
                f"❌ **ᴄᴏɪɴ ᴛɪᴅᴀᴋ ᴄᴜᴋᴜᴘ**\n\nCoin: {user[2]} | Butuh: {COIN_PER_INJECT}",
                [[Button.inline("💰 ᴛᴏᴘ-ᴜᴘ", b"menu_topup")],
                 [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"menu_main")]])
            return

        ok, reason = can_inject(uid)
        if not ok:
            await edit_menu(event.chat_id, menu_msg, f"⏳ **{reason}**", back_button())
            return

        user_states[uid] = {"state": "await_email", "data": {}, "menu_msg": menu_msg}
        await edit_menu(event.chat_id, menu_msg,
            "📧 **Masukkan email CPM:**\n\n_Ketik /cancel untuk batal_", back_button())

    elif data == "menu_profile":
        caption = (
            f"👤 **ᴘʀᴏꜰɪʟᴇ**\n\n"
            f"🆔 `{uid}`\n"
            f"👤 @{user[1] or '-'}\n"
            f"💰 Coin: **{user[2]}**\n"
            f"🎯 Total Inject: **{user[4]}**\n"
            f"👥 Referral: **{user[8]}**\n"
            f"📅 Join: {user[15][:10]}\n"
            + (f"📝 Note: _{user[14]}_\n" if user[14] else "")
        )
        await edit_menu(event.chat_id, menu_msg, caption, back_button())

    elif data == "menu_history":
        rows = db_fetchall(
            "SELECT email, status, timestamp FROM inject_history "
            "WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
        if not rows:
            caption = "📜 **ʜɪꜱᴛᴏʀʏ**\n\n_Belum ada history._"
        else:
            caption = "📜 **ʜɪꜱᴛᴏʀʏ (10 terakhir)**\n\n"
            for r in rows:
                em = r[0]
                masked = em[:3] + "***" + em[em.find("@"):] if "@" in em else em[:3] + "***"
                icon = "✅" if r[1] == "success" else "❌"
                caption += f"{icon} `{masked}` • {r[2][:16]}\n"
        await edit_menu(event.chat_id, menu_msg, caption, back_button())

    elif data == "menu_leaderboard":
        rows = db_fetchall(
            "SELECT user_id, username, total_inject FROM users "
            "ORDER BY total_inject DESC LIMIT 10")
        caption = "🏆 **ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ᴛᴏᴘ ɪɴᴊᴇᴄᴛᴏʀ**\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            m = medals[i] if i < 3 else f"{i+1}."
            caption += f"{m} @{r[1] or r[0]} — **{r[2]}** inject\n"
        if not rows:
            caption += "_Belum ada data._"
        await edit_menu(event.chat_id, menu_msg, caption, back_button())

    elif data == "menu_referral":
        bot_username = (await client.get_me()).username
        link = f"https://t.me/{bot_username}?start=ref_{user[6]}"
        caption = (
            f"👥 **ʀᴇꜰᴇʀʀᴀʟ**\n\n"
            f"Dapatkan **+{REFERRAL_REWARD} coin** untuk setiap teman yang join!\n\n"
            f"🔗 Link referral Anda:\n`{link}`\n\n"
            f"👥 Total referral: **{user[8]}**"
        )
        buttons = [
            [Button.url("📤 ʙᴀɢɪᴋᴀɴ", f"https://t.me/share/url?url={link}")],
            [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"menu_main")],
        ]
        await edit_menu(event.chat_id, menu_msg, caption, buttons)

    elif data == "menu_topup":
        caption = (
            f"💰 **ᴛᴏᴘ-ᴜᴘ ᴄᴏɪɴ**\n\n"
            f"Cara top-up:\n"
            f"1️⃣ Kirim request dengan klik tombol di bawah\n"
            f"2️⃣ Kirim bukti transfer ke admin\n"
            f"3️⃣ Admin akan approve & coin masuk\n\n"
            f"👤 Admin: {get_setting('admin_contact')}"
        )
        buttons = [
            [Button.inline("📝 ʀᴇǫᴜᴇꜱᴛ ᴛᴏᴘ-ᴜᴘ", b"topup_request")],
            [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"menu_main")],
        ]
        await edit_menu(event.chat_id, menu_msg, caption, buttons)

    elif data == "topup_request":
        user_states[uid] = {"state": "await_topup_amount", "data": {}, "menu_msg": menu_msg}
        await edit_menu(event.chat_id, menu_msg,
            "💰 **Masukkan jumlah coin yang mau dibeli:**\n\nContoh: `50`",
            back_button(b"menu_topup"))

    elif data == "menu_join":
        caption = (
            f"📢 **ᴊᴏɪɴ ꜱᴘᴏɴꜱᴏʀ**\n\n"
            f"Join channel untuk dapat **+{SPONSOR_REWARD} coin gratis**!\n\n"
            f"Channel: {get_setting('sponsor_channel')}"
        )
        buttons = [
            [Button.url("📢 ᴊᴏɪɴ", get_setting("sponsor_link"))],
            [Button.inline("✅ ᴠᴇʀɪꜰɪᴋᴀꜱɪ", b"verify_join")],
            [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"menu_main")],
        ]
        await edit_menu(event.chat_id, menu_msg, caption, buttons)

    elif data == "verify_join":
        if user[5] == 1:
            await edit_menu(event.chat_id, menu_msg,
                            "✅ Anda sudah klaim reward sponsor.", back_button())
            return
        if await is_joined(uid):
            new_coins = user[2] + SPONSOR_REWARD
            update_user(uid, coins=new_coins, sponsor_claimed=1)
            await edit_menu(event.chat_id, menu_msg,
                f"✅ **ʙᴇʀʜᴀꜱɪʟ!** +{SPONSOR_REWARD} coin\n💰 Total: **{new_coins}**",
                back_button())
        else:
            buttons = [
                [Button.url("📢 ᴊᴏɪɴ", get_setting("sponsor_link"))],
                [Button.inline("🔄 ᴄᴇᴋ ᴜʟᴀɴɢ", b"verify_join")],
                [Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"menu_main")],
            ]
            await edit_menu(event.chat_id, menu_msg, "❌ Belum join channel.", buttons)

    elif data == "menu_help":
        caption = (
            "❓ **ʜᴇʟᴘ**\n\n"
            "**ᴄᴀʀᴀ ɪɴᴊᴇᴄᴛ:**\n"
            "1. Pastikan coin cukup\n"
            "2. Klik Inject Rank\n"
            "3. Masukkan email & password\n"
            "4. Tunggu, lalu cek in-game\n\n"
            "**ᴅᴀᴘᴀᴛ ᴄᴏɪɴ:**\n"
            f"• Referral (+{REFERRAL_REWARD} coin)\n"
            f"• Join sponsor (+{SPONSOR_REWARD} coin)\n"
            "• Top-up ke admin\n\n"
            "⚠️ Bot tidak menyimpan password."
        )
        await edit_menu(event.chat_id, menu_msg, caption, back_button())

    # ==================== ADMIN ====================
    elif data == "admin_panel" and is_admin(uid):
        admin_states[uid] = {"state": "admin_main", "menu_msg": menu_msg}
        await edit_menu(event.chat_id, menu_msg, "🛡️ **ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ**",
                        admin_panel_buttons())

    elif data.startswith("admin_") and is_admin(uid):
        await handle_admin_callback(uid, event.chat_id, menu_msg, data)


async def handle_admin_callback(uid, chat_id, msg_id, data):
    if data == "admin_stats":
        users = db_fetchall("SELECT * FROM users")
        total = len(users)
        total_coins = sum(u[2] for u in users)
        total_inject = sum(u[4] for u in users)
        banned = sum(1 for u in users if u[3] == 1)
        pending = db_fetch("SELECT COUNT(*) FROM topup_requests WHERE status='pending'")[0]
        today_inj = db_fetch(
            "SELECT COUNT(*) FROM inject_history WHERE timestamp LIKE ?",
            (datetime.now().strftime("%Y-%m-%d") + "%",))[0]
        caption = (
            f"📊 **ꜱᴛᴀᴛɪꜱᴛɪᴋ**\n\n"
            f"👥 User: **{total}** | 🚫 Banned: **{banned}**\n"
            f"💰 Total Coin: **{total_coins}**\n"
            f"🎯 Total Inject: **{total_inject}**\n"
            f"📅 Inject hari ini: **{today_inj}**\n"
            f"⏳ Top-up pending: **{pending}**"
        )
        await edit_menu(chat_id, msg_id, caption,
                        [[Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"admin_panel")]])

    elif data.startswith("admin_users_"):
        page = int(data.split("_")[-1])
        per = 5
        total = db_fetch("SELECT COUNT(*) FROM users")[0]
        rows = db_fetchall("SELECT * FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
                           (per, page * per))
        text = f"👥 **ᴜꜱᴇʀ ʟɪꜱᴛ** (hal {page + 1})\n\n"
        for u in rows:
            st = "🚫" if u[3] == 1 else "✅"
            text += f"{st} `{u[0]}` @{u[1] or '-'} 💰{u[2]} 🎯{u[4]}\n"
        if not rows:
            text += "_Kosong._"
        nav = []
        if page > 0:
            nav.append(Button.inline("⬅️", f"admin_users_{page-1}".encode()))
        if (page + 1) * per < total:
            nav.append(Button.inline("➡️", f"admin_users_{page+1}".encode()))
        buttons = []
        if nav:
            buttons.append(nav)
        buttons.append([Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"admin_panel")])
        await edit_menu(chat_id, msg_id, text, buttons)

    elif data.startswith("admin_topup_"):
        page = int(data.split("_")[-1])
        per = 5
        total = db_fetch("SELECT COUNT(*) FROM topup_requests WHERE status='pending'")[0]
        rows = db_fetchall(
            "SELECT * FROM topup_requests WHERE status='pending' "
            "ORDER BY id DESC LIMIT ? OFFSET ?", (per, page * per))
        text = f"💰 **ᴛᴏᴘᴜᴘ ᴘᴇɴᴅɪɴɢ** (hal {page + 1})\n\n"
        buttons = []
        for r in rows:
            text += f"#{r[0]} | UID `{r[1]}` | {r[2]} coin\n"
            buttons.append([
                Button.inline(f"✅ ᴀᴘᴘʀᴏᴠᴇ #{r[0]}", f"topup_approve_{r[0]}".encode()),
                Button.inline(f"❌ ʀᴇᴊᴇᴄᴛ #{r[0]}", f"topup_reject_{r[0]}".encode()),
            ])
        if not rows:
            text += "_Tidak ada request._"
        nav = []
        if page > 0:
            nav.append(Button.inline("⬅️", f"admin_topup_{page-1}".encode()))
        if (page + 1) * per < total:
            nav.append(Button.inline("➡️", f"admin_topup_{page+1}".encode()))
        if nav:
            buttons.append(nav)
        buttons.append([Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"admin_panel")])
        await edit_menu(chat_id, msg_id, text, buttons)

    elif data.startswith("topup_approve_") and is_admin(uid):
        rid = int(data.split("_")[-1])
        req = db_fetch("SELECT * FROM topup_requests WHERE id=?", (rid,))
        if req and req[5] == "pending":
            u = get_user(req[1])
            if u:
                update_user(req[1], coins=u[2] + req[2])
                db_exec("UPDATE topup_requests SET status='approved' WHERE id=?", (rid,))
                log_admin(uid, "topup_approve", f"req#{rid} user{req[1]} +{req[2]}")
                try:
                    await client.send_message(req[1],
                        f"✅ Top-up disetujui! +{req[2]} coin.")
                except Exception:
                    pass
        await handle_admin_callback(uid, chat_id, msg_id, "admin_topup_0")

    elif data.startswith("topup_reject_") and is_admin(uid):
        rid = int(data.split("_")[-1])
        req = db_fetch("SELECT * FROM topup_requests WHERE id=?", (rid,))
        if req and req[5] == "pending":
            db_exec("UPDATE topup_requests SET status='rejected' WHERE id=?", (rid,))
            log_admin(uid, "topup_reject", f"req#{rid}")
            try:
                await client.send_message(req[1], "❌ Top-up ditolak.")
            except Exception:
                pass
        await handle_admin_callback(uid, chat_id, msg_id, "admin_topup_0")

    elif data == "admin_ban":
        admin_states[uid] = {"state": "await_ban_id", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "🚫 Masukkan user ID:",
                        back_button(b"admin_panel"))

    elif data == "admin_unban":
        admin_states[uid] = {"state": "await_unban_id", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "✅ Masukkan user ID:",
                        back_button(b"admin_panel"))

    elif data == "admin_addcoin":
        admin_states[uid] = {"state": "await_addcoin", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "➕ Format: `user_id jumlah`",
                        back_button(b"admin_panel"))

    elif data == "admin_remcoin":
        admin_states[uid] = {"state": "await_remcoin", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "➖ Format: `user_id jumlah`",
                        back_button(b"admin_panel"))

    elif data == "admin_note":
        admin_states[uid] = {"state": "await_note", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "📝 Format: `user_id catatan`",
                        back_button(b"admin_panel"))

    elif data.startswith("admin_logs_"):
        page = int(data.split("_")[-1])
        per = 8
        total = db_fetch("SELECT COUNT(*) FROM admin_logs")[0]
        rows = db_fetchall("SELECT * FROM admin_logs ORDER BY id DESC LIMIT ? OFFSET ?",
                           (per, page * per))
        text = f"📜 **ᴀᴅᴍɪɴ ʟᴏɢ** (hal {page + 1})\n\n"
        for r in rows:
            text += f"`{r[0]}` [{r[1]}] {r[2]} → {r[3]}\n"
        if not rows:
            text += "_Kosong._"
        nav = []
        if page > 0:
            nav.append(Button.inline("⬅️", f"admin_logs_{page-1}".encode()))
        if (page + 1) * per < total:
            nav.append(Button.inline("➡️", f"admin_logs_{page+1}".encode()))
        buttons = []
        if nav:
            buttons.append(nav)
        buttons.append([Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"admin_panel")])
        await edit_menu(chat_id, msg_id, text, buttons)

    elif data == "admin_broadcast":
        admin_states[uid] = {"state": "await_broadcast", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "📢 Masukkan pesan:",
                        back_button(b"admin_panel"))

    elif data == "admin_export":
        users = db_fetchall("SELECT * FROM users")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["user_id", "username", "coins", "banned", "total_inject",
                    "referral_count", "joined_at"])
        for u in users:
            w.writerow([u[0], u[1], u[2], u[3], u[4], u[8], u[15]])
        data_bytes = io.BytesIO(buf.getvalue().encode())
        data_bytes.name = f"cpmbot_users_{datetime.now().strftime('%Y%m%d')}.csv"
        try:
            await client.send_file(uid, data_bytes, caption="📤 Export user data")
        except Exception:
            pass
        await edit_menu(chat_id, msg_id, "✅ Export terkirim ke chat Anda.",
                        [[Button.inline("🔙 ᴋᴇᴍʙᴀʟɪ", b"admin_panel")]])

    elif data == "admin_settings":
        caption = (
            f"⚙️ **ꜱᴇᴛᴛɪɴɢꜱ**\n\n"
            f"📢 Channel: `{get_setting('sponsor_channel')}`\n"
            f"🔗 Link: `{get_setting('sponsor_link')}`\n"
            f"👤 Contact: `{get_setting('admin_contact')}`\n"
            f"🖼️ Thumb: `{get_setting('thumbnail_url')[:40]}`\n"
            f"🔧 Maintenance: `{'ON' if get_setting('maintenance') == '1' else 'OFF'}`\n"
            f"🔒 Force Join: `{'ON' if get_setting('force_join') == '1' else 'OFF'}`"
        )
        await edit_menu(chat_id, msg_id, caption, settings_buttons())

    elif data == "admin_set_sponsor":
        admin_states[uid] = {"state": "await_set_sponsor", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "📢 Username channel:",
                        back_button(b"admin_settings"))

    elif data == "admin_set_link":
        admin_states[uid] = {"state": "await_set_link", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "🔗 Link channel:",
                        back_button(b"admin_settings"))

    elif data == "admin_set_contact":
        admin_states[uid] = {"state": "await_set_contact", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "👤 Username admin contact:",
                        back_button(b"admin_settings"))

    elif data == "admin_set_thumb":
        admin_states[uid] = {"state": "await_set_thumb", "menu_msg": msg_id}
        await edit_menu(chat_id, msg_id, "🖼️ URL thumbnail baru:",
                        back_button(b"admin_settings"))

    elif data == "admin_toggle_maint":
        cur = get_setting("maintenance")
        set_setting("maintenance", "0" if cur == "1" else "1")
        log_admin(uid, "toggle_maintenance", "on" if cur == "0" else "off")
        await handle_admin_callback(uid, chat_id, msg_id, "admin_settings")

    elif data == "admin_toggle_join":
        cur = get_setting("force_join")
        set_setting("force_join", "0" if cur == "1" else "1")
        log_admin(uid, "toggle_force_join", "on" if cur == "0" else "off")
        await handle_admin_callback(uid, chat_id, msg_id, "admin_settings")


# ==================== TEXT HANDLER ====================
@client.on(events.NewMessage())
async def text_handler(event):
    if event.text and event.text.startswith("/"):
        return

    uid = event.sender_id
    chat_id = event.chat_id

    if is_banned(uid):
        try:
            await event.delete()
        except Exception:
            pass
        return

    # ============ USER ============
    if uid in user_states:
        state = user_states[uid].get("state")
        menu_msg = user_states[uid].get("menu_msg")
        text = event.text.strip()

        if state == "await_email":
            try:
                await event.delete()
            except Exception:
                pass
            user_states[uid]["data"]["email"] = text
            user_states[uid]["state"] = "await_password"
            await edit_menu(chat_id, menu_msg,
                "🔒 **Masukkan password:**\n\n_/cancel untuk batal_", back_button())
            return

        elif state == "await_password":
            password = text
            try:
                await event.delete()
            except Exception:
                pass

            email = user_states[uid]["data"].get("email")
            user = get_user(uid)
            ok, reason = can_inject(uid)
            if not ok:
                await edit_menu(chat_id, menu_msg, f"⏳ {reason}", back_button())
                user_states[uid]["state"] = "main"
                return

            if user[2] < COIN_PER_INJECT:
                await edit_menu(chat_id, menu_msg, "❌ Coin tidak cukup.", back_button())
                user_states[uid]["state"] = "main"
                return

            await edit_menu(chat_id, menu_msg, "⏳ **Memproses...**", [])

            loop = asyncio.get_event_loop()
            token, err = await loop.run_in_executor(None, cpm_login, email, password)
            if not token:
                await edit_menu(chat_id, menu_msg, f"❌ Login gagal:\n`{err}`", back_button())
                add_inject_history(uid, email, "fail")
                user_states[uid]["state"] = "main"
                return

            success, info = await loop.run_in_executor(
                None, cpm_set_rank, token, REAL_ESTATE_VALUE)

            if success:
                new_coins = user[2] - COIN_PER_INJECT
                new_inject = user[4] + 1
                update_user(uid, coins=new_coins, total_inject=new_inject,
                            last_inject=datetime.now().isoformat(),
                            today_inject=user[11] + 1,
                            today_date=datetime.now().strftime("%Y-%m-%d"))
                add_inject_history(uid, email, "success")
                caption = (
                    f"✅ **ɪɴᴊᴇᴄᴛ ʙᴇʀʜᴀꜱɪʟ!**\n\n"
                    f"👑 Rank: **KING**\n"
                    f"🏠 Real Estate: **{REAL_ESTATE_VALUE}**\n"
                    f"🎯 Total Inject: **{new_inject}**\n"
                    f"💰 Sisa Coin: **{new_coins}**"
                )
                await edit_menu(chat_id, menu_msg, caption, back_button())
            else:
                add_inject_history(uid, email, "fail")
                await edit_menu(chat_id, menu_msg, f"❌ Gagal:\n`{info}`", back_button())

            user_states[uid]["state"] = "main"
            return

        elif state == "await_topup_amount":
            try:
                await event.delete()
            except Exception:
                pass
            try:
                amount = int(text)
                if amount < 1 or amount > 100000:
                    raise ValueError
            except ValueError:
                await edit_menu(chat_id, menu_msg, "❌ Jumlah tidak valid.",
                                back_button(b"menu_topup"))
                user_states[uid]["state"] = "main"
                return

            user_states[uid]["data"]["amount"] = amount
            user_states[uid]["state"] = "await_topup_proof"
            await edit_menu(chat_id, menu_msg,
                f"💰 Jumlah: **{amount} coin**\n\n"
                f"📸 Kirim bukti transfer (foto/teks):",
                back_button(b"menu_topup"))
            return

        elif state == "await_topup_proof":
            proof = "image" if event.photo else text
            amount = user_states[uid]["data"].get("amount", 0)
            db_exec(
                "INSERT INTO topup_requests (user_id, amount, price, proof, status, timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (uid, amount, "manual", proof, "pending", datetime.now().isoformat()))
            try:
                await event.delete()
            except Exception:
                pass
            caption = (
                f"✅ **ʀᴇǫᴜᴇꜱᴛ ᴛᴇʀᴋɪʀɪᴍ**\n\n"
                f"💰 Jumlah: **{amount} coin**\n"
                f"⏳ Status: **Pending**\n\n"
                f"Hubungi admin untuk konfirmasi:\n"
                f"👤 {get_setting('admin_contact')}"
            )
            await edit_menu(chat_id, menu_msg, caption, back_button(b"menu_topup"))
            user_states[uid]["state"] = "main"

            for a in ADMIN_IDS:
                try:
                    await client.send_message(a,
                        f"🔔 **Top-up request baru**\n"
                        f"👤 User: `{uid}` @{get_user(uid)[1] or '-'}\n"
                        f"💰 Jumlah: {amount} coin\n"
                        f"📸 Bukti: {proof}")
                except Exception:
                    pass
            return

    # ============ ADMIN ============
    if is_admin(uid) and uid in admin_states:
        state = admin_states[uid].get("state")
        menu_msg = admin_states[uid].get("menu_msg") or get_menu_msg(uid)
        text = event.text.strip()

        try:
            await event.delete()
        except Exception:
            pass

        if not menu_msg:
            menu_msg = await send_main_menu(chat_id, uid)

        if state == "await_ban_id":
            try:
                t = int(text)
                if get_user(t):
                    update_user(t, banned=1)
                    log_admin(uid, "ban", str(t))
                    await edit_menu(chat_id, menu_msg, f"✅ `{t}` dibanned.",
                                    [[Button.inline("🔙", b"admin_panel")]])
                else:
                    await edit_menu(chat_id, menu_msg, "❌ Tidak ditemukan.",
                                    [[Button.inline("🔙", b"admin_panel")]])
            except Exception:
                await edit_menu(chat_id, menu_msg, "❌ ID invalid.",
                                [[Button.inline("🔙", b"admin_panel")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_unban_id":
            try:
                t = int(text)
                if get_user(t):
                    update_user(t, banned=0)
                    log_admin(uid, "unban", str(t))
                    await edit_menu(chat_id, menu_msg, f"✅ `{t}` di-unban.",
                                    [[Button.inline("🔙", b"admin_panel")]])
                else:
                    await edit_menu(chat_id, menu_msg, "❌ Tidak ditemukan.",
                                    [[Button.inline("🔙", b"admin_panel")]])
            except Exception:
                await edit_menu(chat_id, menu_msg, "❌ ID invalid.",
                                [[Button.inline("🔙", b"admin_panel")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_addcoin":
            try:
                p = text.split()
                t, amt = int(p[0]), int(p[1])
                u = get_user(t)
                if u:
                    new = u[2] + amt
                    update_user(t, coins=new)
                    log_admin(uid, "addcoin", f"{t} +{amt}")
                    await edit_menu(chat_id, menu_msg,
                                    f"✅ `{t}` +{amt} coin → {new}",
                                    [[Button.inline("🔙", b"admin_panel")]])
                else:
                    await edit_menu(chat_id, menu_msg, "❌ Tidak ditemukan.",
                                    [[Button.inline("🔙", b"admin_panel")]])
            except Exception:
                await edit_menu(chat_id, menu_msg, "❌ Format: user_id jumlah",
                                [[Button.inline("🔙", b"admin_panel")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_remcoin":
            try:
                p = text.split()
                t, amt = int(p[0]), int(p[1])
                u = get_user(t)
                if u:
                    new = max(0, u[2] - amt)
                    update_user(t, coins=new)
                    log_admin(uid, "remcoin", f"{t} -{amt}")
                    await edit_menu(chat_id, menu_msg,
                                    f"✅ `{t}` -{amt} coin → {new}",
                                    [[Button.inline("🔙", b"admin_panel")]])
                else:
                    await edit_menu(chat_id, menu_msg, "❌ Tidak ditemukan.",
                                    [[Button.inline("🔙", b"admin_panel")]])
            except Exception:
                await edit_menu(chat_id, menu_msg, "❌ Format: user_id jumlah",
                                [[Button.inline("🔙", b"admin_panel")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_note":
            try:
                p = text.split(maxsplit=1)
                t = int(p[0])
                note = p[1] if len(p) > 1 else ""
                if get_user(t):
                    update_user(t, note=note)
                    log_admin(uid, "note", f"{t}: {note[:30]}")
                    await edit_menu(chat_id, menu_msg, f"✅ Note disimpan.",
                                    [[Button.inline("🔙", b"admin_panel")]])
                else:
                    await edit_menu(chat_id, menu_msg, "❌ Tidak ditemukan.",
                                    [[Button.inline("🔙", b"admin_panel")]])
            except Exception:
                await edit_menu(chat_id, menu_msg, "❌ Format: user_id catatan",
                                [[Button.inline("🔙", b"admin_panel")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_broadcast":
            all_u = db_fetchall("SELECT user_id FROM users WHERE banned=0")
            sent = 0
            for u in all_u:
                try:
                    await client.send_message(u[0], f"📢 **ʙʀᴏᴀᴅᴄᴀꜱᴛ:**\n\n{text}")
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
            log_admin(uid, "broadcast", f"{sent} user")
            await edit_menu(chat_id, menu_msg, f"✅ Terkirim ke {sent} user.",
                            [[Button.inline("🔙", b"admin_panel")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_set_sponsor":
            set_setting("sponsor_channel", text)
            log_admin(uid, "set_sponsor", text)
            await edit_menu(chat_id, menu_msg, f"✅ Channel: `{text}`",
                            [[Button.inline("🔙", b"admin_settings")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_set_link":
            set_setting("sponsor_link", text)
            await edit_menu(chat_id, menu_msg, "✅ Link di-set.",
                            [[Button.inline("🔙", b"admin_settings")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_set_contact":
            set_setting("admin_contact", text)
            await edit_menu(chat_id, menu_msg, "✅ Contact di-set.",
                            [[Button.inline("🔙", b"admin_settings")]])
            admin_states[uid]["state"] = "admin_main"

        elif state == "await_set_thumb":
            set_setting("thumbnail_url", text)
            await edit_menu(chat_id, menu_msg, "✅ Thumbnail di-set.",
                            [[Button.inline("🔙", b"admin_settings")]])
            admin_states[uid]["state"] = "admin_main"


# ==================== MAIN ====================
if __name__ == "__main__":
    init_db()
    client.start(bot_token=BOT_TOKEN)
    print("🤖 cpmbot started!")
    client.run_until_disconnected()
