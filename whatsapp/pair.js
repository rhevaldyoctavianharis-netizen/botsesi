/**
 * whatsapp/pair.js  (DIUBAH — tambah metode QR Code selain Pairing Code)
 * Dipanggil sebagai SUBPROCESS PENDEK oleh handlers/whatsapp_gen.py --
 * SATU proses Node terpisah per user yang sedang generate session
 * WhatsApp.
 *
 * Dua metode tautkan perangkat (dipilih user lewat tombol di bot):
 * - "pairing": user masukkan kode 6-karakter di HP-nya (butuh nomor telepon)
 * - "qr"     : user scan gambar QR dari kamera WhatsApp (tanpa nomor telepon)
 *
 * QR di-refresh otomatis oleh WhatsApp tiap ~20-60 detik selama belum
 * di-scan -- setiap kali ada QR baru, kita generate ulang gambarnya dan
 * kirim baris QR: baru, supaya bot bisa update gambar yang dikirim ke
 * user (QR lama jadi kadaluarsa kalau tidak di-refresh).
 *
 * PROTOKOL KOMUNIKASI lewat STDOUT (satu baris = satu event):
 *   PAIRING_CODE:123456    -> (mode pairing) kode 6 digit, teruskan ke user
 *   QR:<base64 PNG>          -> (mode qr) gambar QR baru (bisa muncul >1x)
 *   CONNECTED                -> berhasil link, file kredensial siap
 *   ERROR:<pesan singkat>     -> gagal, sertakan alasannya
 *   TIMEOUT                   -> tidak ada respons dalam batas waktu (2 menit)
 *
 * Argumen CLI: node pair.js <pairing|qr> <nomor_telepon_atau_-> <folder_sesi>
 */

const {
    default: makeWASocket,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    Browsers,
    DisconnectReason,
} = require("@whiskeysockets/baileys");
const pino = require("pino");
const QRCode = require("qrcode");

const method = process.argv[2]; // "pairing" atau "qr"
const phoneNumber = process.argv[3];
const sessionDir = process.argv[4];

const TIMEOUT_MS = 120000; // 2 menit -- berlaku untuk KEDUA metode
const PRE_REQUEST_DELAY_MS = 3000; // jeda supaya koneksi WS settle dulu (mode pairing)

if (!method || !sessionDir || (method === "pairing" && !phoneNumber)) {
    console.log("ERROR:Argumen tidak lengkap.");
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
    sock.ev.on("connection.update", async (update) => {
        const { connection, lastDisconnect, qr } = update;

        // Mode QR: setiap kali WhatsApp kirim string QR baru, generate
        // ulang gambarnya dan kirim ke Python lewat stdout.
        if (method === "qr" && qr) {
            try {
                const buf = await QRCode.toBuffer(qr, { type: "png", width: 320, margin: 1 });
                console.log(`QR:${buf.toString("base64")}`);
            } catch (e) {
                // Gagal generate 1 frame QR -- abaikan, tunggu refresh berikutnya.
            }
        }

        if (connection === "open") {
            clearTimeout(timeoutHandle);
            // Jeda singkat supaya event creds.update terakhir sempat
            // tersimpan ke disk sebelum proses exit.
            setTimeout(() => finish("CONNECTED", 0), 1500);
        } else if (connection === "close") {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            // Kalau koneksi putus SEBELUM pairing code sempat diminta
            // (mode pairing) itu jelas kegagalan -- jangan tunggu
            // TIMEOUT_MS lagi. Mode QR tidak punya tahap "request" jadi
            // syarat ini otomatis dilewati untuk QR.
            const tooEarly = method === "pairing" && !pairingRequested;
            if (!shouldReconnect || tooEarly) {
                clearTimeout(timeoutHandle);
                finish(`ERROR:Koneksi ditutup (kode ${statusCode || "unknown"}).`, 1);
            }
            // Kalau shouldReconnect true, Baileys akan retry sendiri --
            // biarkan sampai berhasil connect atau TIMEOUT_MS tercapai.
        }
    });

    if (method === "pairing" && !sock.authState.creds.registered) {
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
    // Mode "qr": TIDAK memanggil requestPairingCode() sama sekali --
    // Baileys otomatis memancarkan event "qr" lewat connection.update
    // begitu koneksi terbuka dan device belum ter-register.
}

main().catch((err) => {
    finish(`ERROR:${err.message || err}`, 1);
});
