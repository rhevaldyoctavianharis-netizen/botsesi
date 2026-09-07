"""
utils/force_join.py
Fungsi bantu untuk mengecek apakah user sudah join semua channel/grup
yang diwajibkan admin. Daftar channel & status on/off DIAMBIL DARI
utils/settings (live, diatur admin lewat /admin) — bukan lagi hardcode
dari .env, supaya admin bisa menambah/menghapus channel kapan saja
tanpa restart bot.
"""

from telethon import TelegramClient
from telethon.errors import UserNotParticipantError

from telethon.tl.functions.channels import GetParticipantRequest

from utils import settings


async def get_unjoined_channels(client: TelegramClient, user_id: int):
    """Return list channel (dict: username/url/label) yang BELUM di-join
    user. List kosong berarti user lolos semua syarat (atau force join
    sedang dimatikan admin)."""
    if not settings.force_join_enabled():
        return []

    channels = settings.force_join_channels()
    if not channels:
        return []

    unjoined = []
    for ch in channels:
        try:
            entity = await client.get_entity(ch["username"])
            await client(GetParticipantRequest(entity, user_id))
        except UserNotParticipantError:
            unjoined.append(ch)
        except Exception:
            # Channel tidak ditemukan / bot bukan admin di sana / error lain
            # -> fail-open untuk channel ini saja, supaya bot tidak macet total.
            continue
    return unjoined


async def is_member(client: TelegramClient, user_id: int) -> bool:
    unjoined = await get_unjoined_channels(client, user_id)
    return len(unjoined) == 0
