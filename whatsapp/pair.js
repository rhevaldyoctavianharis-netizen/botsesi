/**
 * whatsapp/pair.js  (BARU)
 * Dipanggil sebagai SUBPROCESS PENDEK oleh handlers/whatsapp_gen.py --
 * SATU proses Node terpisah per user yang sedang generate session
 * WhatsApp, supaya banyak user bisa link WhatsApp secara BERSAMAAN
 * tanpa saling ganggu (folder sesi per proses juga terpisah).
 *
 * Ini BUKAN servis Node.js yang jalan terus-menerus -- proses ini exit
 * begitu pairing selesai (berhasil/gagal/timeout), persis seperti
 * subprocess CLI biasa.
 *
 * PROTOKOL KOMUNIKASI lewat STDOUT (satu baris = satu event), dibaca
 * Python baris demi baris:
 *   PAIRING_CODE:123456   -> kode pairing 6 digit, teruskan ke user
 *   CONNECTED              -> berhasil link, file kredensial siap di
 *                             folder sesi yang diberikan lewat argumen
 *   ERROR:<pesan singkat>   -> gagal, sertakan alasannya
 *   TIMEOUT                 -> tidak ada respons dalam batas waktu
 *
 * Argumen CLI: node pair.js <nomor_telepon> <folder_sesi>
 */

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const pino = require("pino");

const phoneNumber = process.argv[2];
const sessionDir = process.argv[3];
const TIMEOUT_MS = 120000; // 2 menit menunggu user memasukkan kode di HP-nya

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

async function main() {
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        browser: ["Botsesi", "Chrome", "1.0.0"],
    });

    sock.ev.on("creds.update", saveCreds);

    const timeoutHandle = setTimeout(() => {
        finish("TIMEOUT", 1);
    }, TIMEOUT_MS);

    // Minta pairing code HANYA kalau device ini belum pernah register.
    if (!sock.authState.creds.registered) {
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
