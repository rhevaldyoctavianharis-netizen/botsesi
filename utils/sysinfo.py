import platform
import socket
import time

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from utils.runtime_info import format_uptime


def _safe(fn, default="N/A"):
    try:
        return fn()
    except Exception:
        return default


def get_system_info_text() -> str:
    lines = ["🖥️ **System Info**", ""]
    lines.append(f"🖥️ Hostname: `{_safe(socket.gethostname)}`")
    lines.append(f"🐧 OS: `{platform.system()} {platform.release()}`")
    lines.append(f"🏗️ Arsitektur: `{platform.machine()}`")
    lines.append(f"🐍 Python: `{platform.python_version()}`")
    lines.append("")

    cpu_model = _safe(lambda: platform.processor()) or "N/A"
    lines.append(f"🧠 CPU: `{cpu_model}`")
    if _PSUTIL_AVAILABLE:
        cores_physical = _safe(lambda: psutil.cpu_count(logical=False))
        cores_logical = _safe(lambda: psutil.cpu_count(logical=True))
        cpu_percent = _safe(lambda: psutil.cpu_percent(interval=0.5))
        lines.append(f"⚙️ Core: `{cores_physical} fisik / {cores_logical} logical`")
        lines.append(f"📈 Pemakaian CPU: `{cpu_percent}%`")
    else:
        lines.append("⚙️ Detail core & pemakaian CPU: `psutil tidak tersedia`")
    lines.append("")

    if _PSUTIL_AVAILABLE:
        vm = _safe(lambda: psutil.virtual_memory())
        if vm != "N/A":
            lines.append(f"💾 RAM: `{vm.used/(1024**3):.2f} GB / {vm.total/(1024**3):.2f} GB ({vm.percent}%)`")
        else:
            lines.append("💾 RAM: `gagal diambil`")
    else:
        lines.append("💾 RAM: `psutil tidak tersedia`")

    if _PSUTIL_AVAILABLE:
        disk = _safe(lambda: psutil.disk_usage("/"))
        if disk != "N/A":
            lines.append(f"💽 Disk: `{disk.used/(1024**3):.2f} GB / {disk.total/(1024**3):.2f} GB ({disk.percent}%)`")
        else:
            lines.append("💽 Disk: `gagal diambil`")
    else:
        lines.append("💽 Disk: `psutil tidak tersedia`")
    lines.append("")

    lines.append(f"⏱️ Bot berjalan sejak: `{format_uptime()}`")
    if _PSUTIL_AVAILABLE:
        boot_ts = _safe(lambda: psutil.boot_time())
        if boot_ts != "N/A":
            sec = int(time.time() - boot_ts)
            d, r = divmod(sec, 86400)
            h, r = divmod(r, 3600)
            m, _ = divmod(r, 60)
            lines.append(f"🖥️ Server aktif sejak boot: `{d}h {h}j {m}m`")

    lines.append("")
    lines.append("_Catatan: kalau bot jalan di Render.com, ini spek container plan kamu, BUKAN device fisik pribadi._")
    return "\n".join(lines)