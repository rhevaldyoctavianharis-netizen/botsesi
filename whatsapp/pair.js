/**
 * whatsapp/pair.js  (DIUBAH — perbaikan bug "gagal tautkan perangkat")
 * Dipanggil sebagai SUBPROCESS PENDEK oleh handlers/whatsapp_gen.py --
 * SATU proses Node terpisah per user yang sedang generate session
 * WhatsApp, supaya banyak user bisa link WhatsApp secara BERSAMAAN
 * tanpa saling ganggu.
 *
 * PERBAIKAN dari versi sebelumnya (penyebab paling umum pairing gagal
 * di Baileys):
 * 1. Tidak fetch versi WhatsApp Web terbaru -> pakai versi bawaan
 *    library yang bisa basi -> koneksi ditolak server WhatsApp.
 *    Sekarang pakai fetchLatestBaileysVersion().
 * 2. Minta pairing code LANGSUNG setelah socket dibuat, padahal koneksi
 *    WebSocket-nya belum tentu sudah settle -> sering gagal dengan
 *    error "Connection Closed" / "Precondition Required". Sekarang ada
 *    jeda singkat sebelum requestPairingCode().
 * 3. Browser descriptor custom diganti pakai helper resmi Browsers.ubuntu()
 *    yang lebih dikenali server WhatsApp.
 *
 * PROTOKOL KOMUNIKASI lewat STDOUT (satu baris = satu event):
 *   PAIRING_CODE:123456   -> kode pairing 6 digit, teruskan ke user
 *   CONNECTED              -> berhasil link, file kredensial siap
 *   ERROR:<pesan singkat>   -> gagal, sertakan alasannya
 *   TIMEOUT                 -> tidak ada respons dalam batas waktu
 *
 * Argumen CLI: node pair.js <nomor_telepon> <folder_sesi>
 */

const {
    default: makeWASocket,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    Browsers,
    DisconnectReason,
} = require("@whiskeysockets/baileys");
const pino = require("pino");

const phoneNumber = process.argv[2];
const sessionDir = process.argv[3];
const TIMEOUT_MS = 120000; // 2 menit menunggu user memasukkan kode di HP-nya
const PRE_REQUEST_DELAY_MS = 3000; // jeda supaya koneksi WS settle dulu

if (!phoneNumber || !sessionDir) {
    console.log("ERROR:Argumen tidak lengkap (butuh nomor telepon & folder sesi).");
    process.exit(1);
}

let finished = false;

function finish(line, exitCode) {
    if (finished) return;
    finished = true;
    console.log(line);
    process.exit(exitCode);
}

function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        browser: Browsers.ubuntu("Chrome"),
    });

    sock.ev.on("creds.update", saveCreds);

    const timeoutHandle = setTimeout(() => {
        finish("TIMEOUT", 1);
    }, TIMEOUT_MS);

    // Minta pairing code HANYA kalau device ini belum pernah register.
    if (!sock.authState.creds.registered) {
        await delay(PRE_REQUEST_DELAY_MS);
        try {
            const cleanNumber = phoneNumber.replace(/[^0-9]/g, "");
            const code = await sock.requestPairingCode(cleanNumber);
            console.log(`PAIRING_CODE:${code}`);
        } catch (err) {
            clearTimeout(timeoutHandle);
            finish(`ERROR:${err.message || err}`, 1);
            return;
        }
    }

    sock.ev.on("connection.update", (update) => {
        const { connection, lastDisconnect } = update;

        if (connection === "open") {
            clearTimeout(timeoutHandle);
            // Jeda singkat supaya event creds.update terakhir sempat
            // tersimpan ke disk sebelum proses exit.
            setTimeout(() => finish("CONNECTED", 0), 1500);
        } else if (connection === "close") {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            if (!shouldReconnect) {
                clearTimeout(timeoutHandle);
                finish(`ERROR:Koneksi ditutup (kode ${statusCode || "unknown"}).`, 1);
            }
            // Kalau shouldReconnect true, Baileys akan retry sendiri --
            // biarkan sampai berhasil connect atau TIMEOUT_MS tercapai.
        }
    });
}

main().catch((err) => {
    finish(`ERROR:${err.message || err}`, 1);
});
