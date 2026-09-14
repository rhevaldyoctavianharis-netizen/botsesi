/**
 * whatsapp/pair.js  (DIUBAH — urutan listener diperbaiki + browser descriptor)
 * Dipanggil sebagai SUBPROCESS PENDEK oleh handlers/whatsapp_gen.py --
 * SATU proses Node terpisah per user yang sedang generate session
 * WhatsApp.
 *
 * PERBAIKAN dari versi sebelumnya:
 * 1. Listener "connection.update" SEKARANG didaftarkan SEBELUM minta
 *    pairing code (bukan sesudah) -- sebelumnya ada jendela waktu
 *    (delay 3 detik + request pairing code) di mana event koneksi bisa
 *    terjadi TAPI listener belum terpasang, jadi terlewat begitu saja.
 * 2. Browser descriptor diganti ke Browsers.macOS("Desktop") -- sesuai
 *    contoh resmi Baileys untuk alur pairing code; beberapa laporan
 *    komunitas menyebut descriptor custom/Ubuntu kurang konsisten
 *    dikenali WhatsApp khusus untuk metode pairing code.
 * 3. Hapus opsi `printQRInTerminal` yang sudah deprecated di Baileys
 *    versi baru (kita memang tidak pakai QR sama sekali).
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
let pairingRequested = false;

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
        logger: pino({ level: "silent" }),
        browser: Browsers.macOS("Desktop"),
    });

    sock.ev.on("creds.update", saveCreds);

    const timeoutHandle = setTimeout(() => {
        finish("TIMEOUT", 1);
    }, TIMEOUT_MS);

    // PENTING: listener ini WAJIB dipasang SEBELUM requestPairingCode(),
    // supaya event "close" yang mungkin terjadi selagi menunggu jeda /
    // menunggu respons requestPairingCode() tidak terlewat.
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
            // Kalau koneksi putus SEBELUM pairing code sempat diminta,
            // itu jelas kegagalan -- jangan tunggu TIMEOUT_MS lagi.
            if (!shouldReconnect || !pairingRequested) {
                clearTimeout(timeoutHandle);
                finish(`ERROR:Koneksi ditutup (kode ${statusCode || "unknown"}).`, 1);
            }
            // Kalau shouldReconnect true DAN pairing code sudah diminta,
            // Baileys akan retry sendiri -- biarkan sampai berhasil
            // connect atau TIMEOUT_MS tercapai.
        }
    });

    // Minta pairing code HANYA kalau device ini belum pernah register.
    if (!sock.authState.creds.registered) {
        await delay(PRE_REQUEST_DELAY_MS);
        try {
            const cleanNumber = phoneNumber.replace(/[^0-9]/g, "");
            const code = await sock.requestPairingCode(cleanNumber);
            pairingRequested = true;
            console.log(`PAIRING_CODE:${code}`);
        } catch (err) {
            clearTimeout(timeoutHandle);
            finish(`ERROR:${err.message || err}`, 1);
            return;
        }
    }
}

main().catch((err) => {
    finish(`ERROR:${err.message || err}`, 1);
});
