"""
utils/state.py
Menyimpan status background task per user_id, supaya:
1. Satu user tidak bisa membuka 2 proses generate sekaligus (anti spam).
2. User bisa membatalkan task yang sedang berjalan (tombol Batalkan).

Ini murni in-memory (dict). Karena tiap proses generate dijalankan lewat
asyncio.create_task, banyak user bisa diproses BERSAMAAN tanpa saling
menunggu satu sama lain.
"""

import asyncio
from typing import Dict, Optional

# user_id -> asyncio.Task
_active_tasks: Dict[int, asyncio.Task] = {}


def is_busy(user_id: int) -> bool:
    task = _active_tasks.get(user_id)
    return task is not None and not task.done()


def register_task(user_id: int, task: asyncio.Task) -> None:
    _active_tasks[user_id] = task
    task.add_done_callback(lambda _t: _active_tasks.pop(user_id, None))


def cancel_task(user_id: int) -> bool:
    task = _active_tasks.get(user_id)
    if task and not task.done():
        task.cancel()
        return True
    return False


def get_task(user_id: int) -> Optional[asyncio.Task]:
    return _active_tasks.get(user_id)
