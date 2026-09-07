"""
keep_alive.py  (DIUBAH — tambah self-ping anti-sleep)
Web server ringan (aiohttp) untuk Render.com Web Service, DITAMBAH
loop self-ping yang secara berkala mengakses URL publik service ini
sendiri, supaya Render tidak menganggapnya idle dan mematikannya
(Render Free Plan: auto-sleep setelah 15 menit tanpa HTTP request masuk).

CATATAN JUJUR: ini workaround yang umum dipakai komunitas, TAPI Render
sendiri tidak secara resmi mendukung/menjamin cara ini terus bekerja —
untuk servis yang benar-benar butuh always-on tanpa kompromi, upgrade ke
plan berbayar (Starter ke atas) tetap yang paling reliable. Kode ini
TIDAK menyamar sebagai identitas/layanan lain — cukup mengirim request
dengan User-Agent yang jelas mengidentifikasi dirinya sendiri, karena
Render tidak membedakan traffic "asli user" vs traffic lain untuk urusan
spin-down; yang dicek murni ada-tidaknya HTTP request masuk.
"""

import asyncio
import logging

from aiohttp import web, ClientSession, ClientTimeout

from config import PORT, SELF_PING_URL, SELF_PING_INTERVAL

logger = logging.getLogger("session-bot.keepalive")

_SELF_PING_HEADERS = {"User-Agent": "botsesi-keepalive-selfping/1.0"}


async def _handle_root(request):
    return web.Response(text="Session Generator Bot is running.")


async def _handle_health(request):
    return web.json_response({"status": "ok"})


async def _self_ping_loop():
    """Ping URL publik service ini sendiri tiap SELF_PING_INTERVAL detik
    (default 10 menit, di bawah batas 15 menit Render) supaya service
    tidak pernah dianggap idle. Berjalan selama proses bot hidup; kalau
    satu ping gagal (mis. koneksi internet server bermasalah sesaat),
    loop TETAP lanjut ke ping berikutnya -- tidak boleh sampai bikin bot
    crash gara-gara ini."""
    if not SELF_PING_URL:
        logger.info("ℹ️ Self-ping tidak aktif (bukan di Render / RENDER_EXTERNAL_URL kosong).")
        return

    logger.info(f"🔁 Self-ping aktif: {SELF_PING_URL} tiap {SELF_PING_INTERVAL} detik.")

    async with ClientSession(headers=_SELF_PING_HEADERS, timeout=ClientTimeout(total=20)) as session:
        while True:
            await asyncio.sleep(SELF_PING_INTERVAL)
            try:
                async with session.get(SELF_PING_URL) as resp:
                    logger.info(f"🔁 Self-ping -> HTTP {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Self-ping gagal (diabaikan, lanjut ke ping berikutnya): {e}")


async def start_keep_alive():
    app = web.Application()
    app.router.add_get("/", _handle_root)
    app.router.add_get("/health", _handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logger.info(f"🌐 Keep-alive server jalan di port {PORT} (dibutuhkan Render.com Web Service).")

    # Dijalankan sebagai background task terpisah, TIDAK di-await, supaya
    # tidak memblok startup bot menunggu ping pertama (yang baru terjadi
    # setelah SELF_PING_INTERVAL detik).
    asyncio.create_task(_self_ping_loop())
