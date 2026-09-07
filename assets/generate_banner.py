"""
assets/generate_banner.py
Jalankan sekali (python assets/generate_banner.py) untuk membuat ulang
banner.png yang dikirim bot saat /start. File banner.png hasilnya
sudah disertakan di folder ini, jadi step ini opsional.
"""

import os
from PIL import Image, ImageDraw, ImageFont


def _font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate(path="banner.png"):
    W, H = 1280, 640
    top = (20, 22, 46)
    bottom = (64, 20, 110)
    img = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        ratio = y / H
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # dekorasi lingkaran transparan
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse([-150, -150, 350, 350], fill=(120, 90, 255, 60))
    odraw.ellipse([W - 300, H - 300, W + 150, H + 150], fill=(90, 180, 255, 50))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    title_font = _font(72, bold=True)
    sub_font = _font(30)
    tag_font = _font(26)

    title = "SESSION GENERATOR"
    draw.text((W / 2, 230), title, font=title_font, fill=(255, 255, 255), anchor="mm")

    sub = "🔑 Telethon  •  Pyrogram"
    draw.text((W / 2, 310), sub, font=sub_font, fill=(210, 210, 255), anchor="mm")

    tag = "Fast  •  Secure  •  Interactive"
    draw.text((W / 2, 360), tag, font=tag_font, fill=(180, 180, 220), anchor="mm")

    # garis pemisah
    draw.line([(W / 2 - 200, 400), (W / 2 + 200, 400)], fill=(255, 255, 255, 80), width=2)

    footer = "Powered by Telethon & Pyrogram"
    draw.text((W / 2, 440), footer, font=tag_font, fill=(150, 150, 190), anchor="mm")

    img.save(path)
    print(f"Banner tersimpan di: {path}")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "banner.png")
    generate(out)
