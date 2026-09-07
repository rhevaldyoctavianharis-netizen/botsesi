# 🔑 Telegram Session Generator Bot

Bot Telegram modular untuk generate **session string** (Telethon & Pyrogram)
secara interaktif, lengkap dengan force-join channel/grup, panel **admin
penuh** untuk kontrol semua fitur secara live, dan siap **deploy ke
Render.com**.

## ✨ Fitur

- `/start` menampilkan banner, info pembuat, library yang dipakai, dan cara pakai
- Force-join **multi channel/grup** sebelum bisa memakai bot (bisa diatur admin, on/off + tombol cek ulang)
- Generate session **Telethon** atau **Pyrogram**, alur: nomor telp → OTP → password (jika 2FA)
- Setiap proses generate berjalan sebagai `asyncio.Task` terpisah per user
  → user lain tetap dilayani instan, tidak perlu antre
- Tombol batalkan proses kapan saja
- **Panel Admin (`/admin`)** — kontrol 100% tanpa edit kode / restart bot:
  - Aktif/nonaktif force-join, tambah/hapus channel & grup wajib
  - Aktif/nonaktif fitur generate Telethon & Pyrogram secara terpisah
  - Edit teks pesan Welcome & About (atau reset ke default)
  - Broadcast pesan ke semua user yang pernah `/start`
  - Mode Maintenance (matikan sementara akses untuk non-admin)
  - Tambah/hapus admin tambahan
  - Statistik singkat bot
- **Pilihan bahasa (183 kode ISO 639-1)** — tombol 🌐 Bahasa di menu utama, tersimpan permanen per user di `data/settings.json`, tidak reset walau bot restart/dibuka lagi kapan pun. Bahasa awal dideteksi otomatis dari `lang_code` Telegram user saat `/start` pertama kali.
- Struktur kode modular: `config.py`, `handlers/`, `utils/`
- Siap deploy ke **Render.com** (web server keep-alive bawaan + `render.yaml`)
- Dioptimasi untuk **concurrency tinggi** (`sequential_updates=False` + background task per user) — banyak user bisa generate session/pakai panel admin bersamaan tanpa antre

## 📁 Struktur Folder

```
botsesi/
├── main.py                  # entry point
├── keep_alive.py             # web server kecil untuk Render.com
├── config.py                # semua konfigurasi (.env)
├── .env.example              # contoh isi .env
├── requirements.txt
├── Procfile                  # untuk platform berbasis Procfile
├── render.yaml                # blueprint deploy Render.com
├── runtime.txt                # versi Python untuk Render
├── data/
│   └── settings.json          # pengaturan live (dibuat otomatis saat run pertama)
├── assets/
│   ├── banner.png            # thumbnail menu /start
│   └── generate_banner.py    # script regenerasi banner (opsional)
├── handlers/
│   ├── start.py              # /start, force join, menu about
│   ├── callbacks.py          # dispatcher menu & background task generate
│   ├── admin.py               # panel /admin — kontrol penuh bot
│   └── session_gen.py        # logic generate session Telethon/Pyrogram
└── utils/
    ├── keyboards.py          # semua layout inline button (user & admin)
    ├── force_join.py         # cek keanggotaan multi channel/grup
    ├── state.py               # tracker task per user (anti-spam, cancel)
    ├── db.py                  # penyimpanan JSON untuk pengaturan live
    └── settings.py             # API tingkat-tinggi di atas db.py
```

## 🚀 Cara Menjalankan (Lokal)

1. **Install dependency**
   ```bash
   pip install -r requirements.txt
   ```

2. **Siapkan API credentials**
   - Buat bot lewat [@BotFather](https://t.me/BotFather) → dapatkan `BOT_TOKEN`
   - Buka [my.telegram.org](https://my.telegram.org) → dapatkan `API_ID` & `API_HASH`
   - Cek User ID Telegram kamu sendiri lewat bot seperti `@userinfobot` → dipakai untuk `ADMIN_IDS`

3. **Konfigurasi**
   ```bash
   cp .env.example .env
   ```
   Lalu isi `.env`:
   ```
   BOT_TOKEN=isi_token_botfather
   API_ID=isi_api_id
   API_HASH=isi_api_hash
   FORCE_JOIN=true
   ADMIN_CHANNEL=username_channel_tanpa_at
   ADMIN_CHANNEL_URL=https://t.me/username_channel
   ADMIN_IDS=user_id_kamu
   OWNER_NAME=Nama Kamu
   OWNER_USERNAME=username_telegram_kamu
   ```
   `ADMIN_CHANNEL`/`ADMIN_CHANNEL_URL` hanya dipakai sebagai channel awal
   (sekali migrasi otomatis) — setelah itu semua channel wajib dikelola
   lewat `/admin`, bukan lewat `.env` lagi.

4. **Pastikan bot jadi admin** di setiap channel/grup yang dipakai untuk force-join (supaya bisa mengecek member).

5. **Jalankan bot**
   ```bash
   python main.py
   ```

## 👮 Panel Admin

Kirim `/admin` ke bot dari akun yang User ID-nya terdaftar di `ADMIN_IDS`
(atau ditambahkan lewat menu **Kelola Admin**). Panel ini murni inline
button + beberapa pertanyaan teks singkat (mirip alur generate session),
tidak butuh command hafalan.

Menu yang tersedia:

| Menu | Fungsi |
|---|---|
| 📊 Statistik | Jumlah user, status force join, status fitur, jumlah admin |
| 📢 Force Join | Toggle on/off + tambah/hapus channel atau grup wajib join |
| 🔧 Fitur Generate | Toggle on/off Telethon & Pyrogram secara terpisah |
| 📝 Edit Pesan | Ubah teks Welcome & About, atau reset ke default |
| 📣 Broadcast | Kirim pesan teks ke semua user yang pernah `/start` |
| 🛑/🟢 Mode Maintenance | Matikan sementara akses bot untuk semua non-admin |
| 👮 Kelola Admin | Tambah/hapus admin tambahan (selain dari `.env`) |

Semua perubahan tersimpan di `data/settings.json` dan **langsung berlaku**
untuk request berikutnya — tidak perlu restart bot.

> ⚠️ Admin yang didaftarkan lewat `ADMIN_IDS` di `.env` tidak bisa dihapus
> lewat panel (by design, supaya kamu tidak terkunci dari bot sendiri).
> Untuk menghapusnya, edit `.env` / Environment Variables secara manual.

## ☁️ Deploy ke Render.com

Bot ini polling ke Telegram (bukan webhook), tapi Render mewajibkan
**Web Service** untuk membuka port HTTP. `keep_alive.py` sudah menangani
ini otomatis dengan menjalankan web server kecil di `$PORT` (Render
mengisinya sendiri) — tidak perlu konfigurasi tambahan.

### Opsi A — Blueprint otomatis (`render.yaml`)

1. Push repo ini ke GitHub/GitLab.
2. Di dashboard Render: **New +** → **Blueprint** → pilih repo ini.
3. Render akan otomatis baca `render.yaml` dan membuat service bertipe
   **Web Service** dengan plan **Free**.
4. Isi Environment Variables yang diminta (`BOT_TOKEN`, `API_ID`,
   `API_HASH`, `ADMIN_IDS`, `ADMIN_CHANNEL`, dll) di tab **Environment**.
5. Deploy. Cek log — kalau muncul `✅ Bot berhasil dijalankan`, bot sudah aktif.

### Opsi B — Manual (tanpa Blueprint)

1. **New +** → **Web Service** → hubungkan repo.
2. **Environment**: `Python 3`
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `python main.py`
5. **Health Check Path**: `/health`
6. Tambahkan semua Environment Variables dari `.env.example`.
7. Deploy.

### Catatan penting Render (Free Plan)

- **Disk ephemeral**: `data/settings.json` (pengaturan admin) akan
  **ter-reset ke default setiap kali service di-redeploy** (bukan saat
  restart/wake biasa). Kalau butuh pengaturan yang benar-benar permanen
  lintas redeploy, gunakan Render **Persistent Disk** (paid) atau
  pindahkan `utils/db.py` ke database eksternal (mis. PostgreSQL/Redis).
- **Sleep on idle**: Free Web Service Render bisa "tidur" kalau tidak ada
  traffic HTTP masuk. Karena bot ini polling terus-menerus, ini biasanya
  bukan masalah besar, tapi kalau bot sempat idle lama, service bisa
  di-restart otomatis oleh Render — proses generate yang sedang berjalan
  saat itu akan terputus.
- File session Telethon (`bot_session.session`) juga ikut hilang saat
  redeploy di plan gratis; bot akan login ulang otomatis pakai `BOT_TOKEN`
  saat start, jadi ini aman.

## 🧩 Cara Kerja Background Task

Saat user menekan tombol *Generate Session Now*, `handlers/callbacks.py`
membungkus proses login (`handlers/session_gen.py`) dengan:

```python
task = asyncio.create_task(run_generate_session(bot, event, library))
state.register_task(user_id, task)
```

Karena dijalankan sebagai task terpisah dan berbasis `asyncio`/`Telethon`
yang non-blocking, bot tetap bisa merespon `/start` atau tombol dari user
lain walau ada user lain yang sedang menunggu input OTP. Alur percakapan
di panel admin (tambah channel, edit pesan, broadcast, dll) memakai pola
yang sama supaya bot tetap responsif selagi menunggu balasan admin.

## 🌐 Fitur Bahasa

- Tombol **🌐 Bahasa** di menu utama membuka daftar 183 bahasa (kode ISO 639-1) dengan pagination (10 bahasa/halaman).
- Begitu user memilih, preferensinya disimpan ke `data/settings.json` (`user_languages: {"<user_id>": "<kode>"}`) lewat `utils/settings.py` — **permanen**, tidak reset saat bot restart maupun saat user membuka bot lagi kapan pun.
- Saat `/start` pertama kali, bot otomatis mendeteksi bahasa dari `lang_code` akun Telegram user sebagai nilai awal (kalau valid), supaya user tidak perlu set manual dari awal.
- **Batasan jujur**: menyimpan preferensi bahasa jalan penuh untuk ke-183 bahasa, tapi **terjemahan penuh isi bot** (welcome, about, semua tombol) baru tersedia untuk ~20 bahasa populer di `utils/translations.py` (id, en, ar, es, fr, de, pt, ru, zh, hi, ja, ko, tr, vi, th, bn, ur, fa, nl, it, ms). Bahasa lain tetap tersimpan benar, hanya pesan konfirmasinya fallback ke format netral sampai ditambahkan manual ke `utils/translations.py`. Menerjemahkan seluruh isi bot secara akurat ke 183 bahasa sekaligus bukan sesuatu yang saya kerjakan asal-asalan — silakan tambah bertahap sesuai kebutuhan userbase kamu.

## ⚡ Concurrency / Anti-Antre

- `main.py` membuat `TelegramClient(..., sequential_updates=False)` — Telethon men-dispatch setiap update (pesan/klik tombol) sebagai task `asyncio` terpisah, bukan diproses satu per satu secara berurutan.
- Proses yang butuh menunggu balasan user (generate session, alur admin: tambah channel, edit pesan, broadcast, tambah admin) sudah dibungkus `asyncio.create_task(...)` sejak awal — jadi selagi User A sedang mengetik OTP, User B tetap bisa pakai bot secara instan di chat terpisah.
- **Catatan teknis penting**: ini concurrency berbasis **asyncio single-thread** (cooperative multitasking), BUKAN multi-threading OS sungguhan. Untuk bot I/O-bound seperti ini (mayoritas waktu menunggu jaringan Telegram), asyncio sudah merupakan pendekatan yang tepat dan efisien — menambah OS thread sungguhan justru tidak akan membuat bot Telethon lebih cepat, karena library ini memang didesain async dari awal, bukan thread-safe.

## 🐛 Perbaikan Bug (v2)

- Ditemukan & diperbaiki: `ValueError: No message was sent previously` yang muncul saat generate session maupun di beberapa alur admin (tambah channel, edit pesan, broadcast, tambah admin). Penyebabnya: prompt pertanyaan dikirim lewat `bot.send_message()` langsung, padahal `conv.get_response()` butuh pesan yang dikirim lewat objek `conv` (`conv.send_message()`) supaya Telethon tahu balasan mana yang sedang ditunggu. Semua titik yang terdampak sudah diperbaiki.

## ⚠️ Catatan Keamanan

- Session string setara password akun. Kode ini **tidak menyimpan**
  session string di server manapun — hanya dikirim langsung ke user
  lewat chat, lalu dibuang dari memori.
- Selalu ingatkan user untuk menghapus chat berisi session string setelah disimpan.
- Jangan deploy bot ini untuk menggenerate session akun **orang lain** tanpa izin.
  Fitur ini ditujukan agar user membuat session untuk **akun miliknya sendiri**.
- Jaga `ADMIN_IDS` dan `.env` kamu — siapa pun dengan akses `/admin` bisa
  mengubah seluruh perilaku bot dan mem-broadcast ke semua user.

## 🛠️ Kustomisasi

- Ubah teks/menu default → `handlers/start.py` (bisa juga di-override live lewat `/admin`)
- Ubah layout tombol → `utils/keyboards.py`
- Ganti banner → edit & jalankan ulang `assets/generate_banner.py`, atau ganti file `assets/banner.png` manual
