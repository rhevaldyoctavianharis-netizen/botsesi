import time

START_TIME = time.time()


def get_uptime_seconds() -> float:
    return time.time() - START_TIME


def format_uptime() -> str:
    total = int(get_uptime_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} hari")
    if hours:
        parts.append(f"{hours} jam")
    if minutes:
        parts.append(f"{minutes} menit")
    if not parts:
        parts.append(f"{seconds} detik")
    return " ".join(parts)