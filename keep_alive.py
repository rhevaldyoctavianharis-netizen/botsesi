"""
keep_alive.py
Web server super ringan (aiohttp) yang HANYA dipakai supaya Render.com
(tipe service "Web Service") mendeteksi ada port terbuka.

Bot Telegram-nya sendiri jalan lewat polling (Telethon), bukan lewat
HTTP, jadi endpoint di sini tidak melakukan apa-apa selain membalas
"OK" — ini murni supaya health check Render lolos dan service tidak
dianggap mati.
"""

import logging

from aiohttp import web

from config import PORT

logger = logging.getLogger("session-bot.keepalive")


async def _handle_root(request):
    return web.Response(text="Session Generator Bot is running.")


async def _handle_health(request):
    return web.json_response({"status": "ok"})


async def start_keep_alive():
    app = web.Application()
    app.router.add_get("/", _handle_root)
    app.router.add_get("/health", _handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logger.info(f"🌐 Keep-alive server jalan di port {PORT} (dibutuhkan Render.com Web Service).")
