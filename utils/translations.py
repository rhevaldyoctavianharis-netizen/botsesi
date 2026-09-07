"""
utils/translations.py
Teks konfirmasi setelah user memilih bahasa dari menu 🌐 Bahasa.

PENTING (baca ini): bot BISA menyimpan preferensi untuk SEMUA ~180 kode
bahasa di utils/languages.py — itu jalan penuh untuk semua bahasa. Yang
BELUM tersedia adalah terjemahan penuh seluruh teks bot (welcome, about,
tombol, dsb) ke semua bahasa tersebut; menerjemahkan ratusan baris teks
ke 180 bahasa secara akurat itu pekerjaan besar tersendiri, jadi untuk
sekarang hanya pesan konfirmasi singkat ini yang diterjemahkan, untuk
~20 bahasa populer. Bahasa lain tetap tersimpan dengan benar dan tidak
akan reset, hanya saja pesan konfirmasinya fallback ke format netral
(Indonesia + Inggris) sampai ditambahkan ke dict di bawah.

Cara menambah bahasa baru: tambahkan entry baru "<kode>": "<teks>" ke
LANG_SAVED di bawah.
"""

LANG_SAVED = {
    "id": "✅ Bahasa berhasil diatur ke **Bahasa Indonesia**.",
    "en": "✅ Language successfully set to **English**.",
    "ar": "✅ تم تعيين اللغة إلى **العربية** بنجاح.",
    "es": "✅ Idioma configurado correctamente a **Español**.",
    "fr": "✅ Langue définie avec succès sur **Français**.",
    "de": "✅ Sprache erfolgreich auf **Deutsch** eingestellt.",
    "pt": "✅ Idioma definido com sucesso para **Português**.",
    "ru": "✅ Язык успешно изменён на **Русский**.",
    "zh": "✅ 语言已成功设置为**中文**。",
    "hi": "✅ भाषा सफलतापूर्वक **हिन्दी** पर सेट कर दी गई है।",
    "ja": "✅ 言語が**日本語**に設定されました。",
    "ko": "✅ 언어가 **한국어**로 설정되었습니다.",
    "tr": "✅ Dil başarıyla **Türkçe** olarak ayarlandı.",
    "vi": "✅ Đã đặt ngôn ngữ thành **Tiếng Việt**.",
    "th": "✅ ตั้งค่าภาษาเป็น**ภาษาไทย**เรียบร้อยแล้ว",
    "bn": "✅ ভাষা সফলভাবে **বাংলা** তে সেট করা হয়েছে।",
    "ur": "✅ زبان کامیابی سے **اردو** پر مقرر کر دی گئی ہے۔",
    "fa": "✅ زبان با موفقیت به **فارسی** تنظیم شد.",
    "nl": "✅ Taal succesvol ingesteld op **Nederlands**.",
    "it": "✅ Lingua impostata correttamente su **Italiano**.",
    "ms": "✅ Bahasa berjaya ditetapkan kepada **Bahasa Melayu**.",
}


def lang_saved_text(code: str, language_name: str) -> str:
    if code in LANG_SAVED:
        return LANG_SAVED[code]
    return (
        f"✅ Language preference saved: **{language_name}** (`{code}`).\n"
        "_(Terjemahan penuh untuk bahasa ini belum tersedia, tapi pilihan "
        "kamu sudah tersimpan permanen dan tidak akan reset.)_"
    )
