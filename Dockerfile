# Dockerfile  (BARU)
# Image ini menjalankan BOT PYTHON sebagai proses utama. Node.js hanya
# dipakai untuk menjalankan whatsapp/pair.js sebagai SUBPROCESS PENDEK
# per user (bukan servis long-running terpisah) -- lihat
# handlers/whatsapp_gen.py.
#
# Kenapa Docker? Runtime "Python" native di Render.com tidak menyediakan
# Node.js, padahal Baileys (library WhatsApp Multi-Device) itu library
# Node.js. Jadi kita build image sendiri yang berisi Python + Node.js
# sekaligus.

FROM python:3.11-slim

# ---- Install Node.js 20.x LTS (dibutuhkan Baileys) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Install dependency Python dulu (layer cache terpisah dari source code) ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Install dependency Node.js (Baileys) ----
COPY whatsapp/package.json ./whatsapp/package.json
RUN cd whatsapp && npm install --omit=dev

# ---- Copy seluruh source code ----
COPY . .

ENV PYTHONUNBUFFERED=1

# Render.com otomatis mengisi $PORT dan meneruskannya ke container ini;
# keep_alive.py sudah baca dari environment variable tersebut.
CMD ["python", "main.py"]
