#!/usr/bin/env python3
"""Generate a clean three-light installer icon for Codex Traffic Light."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
PNG_PATH = ROOT / "codex_traffic_light_installer_icon.png"
ICO_PATH = ROOT / "codex_traffic_light_installer.ico"


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def draw_centered_textured_lens(
    base: Image.Image,
    center: tuple[int, int],
    radius: int,
    fill: str,
    glow: str,
) -> None:
    cx, cy = center

    glow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.ellipse(
        (cx - radius - 28, cy - radius - 28, cx + radius + 28, cy + radius + 28),
        fill=rgba(glow, 105),
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(26))
    base.alpha_composite(glow_layer)

    draw = ImageDraw.Draw(base)
    draw.ellipse(
        (cx - radius - 20, cy - radius - 20, cx + radius + 20, cy + radius + 20),
        fill=rgba("#070b12"),
        outline=rgba("#53606e"),
        width=14,
    )
    draw.ellipse(
        (cx - radius - 8, cy - radius - 8, cx + radius + 8, cy + radius + 8),
        fill=rgba("#182232"),
        outline=rgba("#b9c5d3", 190),
        width=6,
    )
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=rgba(fill),
        outline=rgba("#f5f8fb", 220),
        width=7,
    )

    inner = Image.new("RGBA", base.size, (0, 0, 0, 0))
    inner_draw = ImageDraw.Draw(inner)
    for step in range(radius, 0, -3):
        ratio = step / radius
        alpha = int(22 * (1 - ratio) + 32)
        inner_draw.ellipse(
            (cx - step, cy - step, cx + step, cy + step),
            outline=rgba("#ffffff", alpha),
            width=2,
        )
    inner = inner.filter(ImageFilter.GaussianBlur(0.5))
    base.alpha_composite(inner)

    shine = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shine_draw = ImageDraw.Draw(shine)
    shine_draw.ellipse(
        (cx - radius + 18, cy - radius + 16, cx - radius + 70, cy - radius + 68),
        fill=(255, 255, 255, 185),
    )
    shine_draw.ellipse(
        (cx - radius + 36, cy - radius + 8, cx + radius - 16, cy - radius + 58),
        fill=(255, 255, 255, 54),
    )
    shine = shine.filter(ImageFilter.GaussianBlur(2.1))
    base.alpha_composite(shine)

    draw = ImageDraw.Draw(base)
    draw.arc(
        (cx - radius + 7, cy - radius + 8, cx + radius - 6, cy + radius - 5),
        start=295,
        end=72,
        fill=(255, 255, 255, 185),
        width=7,
    )
    draw.arc(
        (cx - radius + 12, cy - radius + 11, cx + radius - 12, cy + radius - 12),
        start=92,
        end=213,
        fill=(0, 0, 0, 90),
        width=6,
    )


def main() -> None:
    canvas_size = 1024
    icon = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    shadow = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((253, 62, 771, 968), radius=122, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    icon.alpha_composite(shadow)

    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((226, 34, 798, 946), radius=140, fill=rgba("#0f151e"), outline=rgba("#5f6d7b"), width=22)
    draw.rounded_rectangle((260, 68, 764, 912), radius=104, fill=rgba("#151d29"), outline=rgba("#2e3a48"), width=10)
    draw.rounded_rectangle((293, 96, 731, 884), radius=82, fill=rgba("#101722"), outline=rgba("#1f2b38"), width=8)

    for y in (255, 512, 769):
        draw.ellipse((330, y - 136, 694, y + 136), fill=rgba("#070b12"), outline=rgba("#394655"), width=18)

    draw_centered_textured_lens(icon, (512, 255), 104, "#ff453a", "#ff342e")
    draw_centered_textured_lens(icon, (512, 512), 104, "#ffd60a", "#d99a00")
    draw_centered_textured_lens(icon, (512, 769), 104, "#32d74b", "#10b248")

    vignette = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    vignette_draw = ImageDraw.Draw(vignette)
    vignette_draw.rounded_rectangle((226, 34, 798, 946), radius=140, outline=(255, 255, 255, 45), width=6)
    vignette_draw.rounded_rectangle((246, 54, 778, 926), radius=123, outline=(0, 0, 0, 85), width=8)
    icon.alpha_composite(vignette)

    icon.save(PNG_PATH)
    icon.save(
        ICO_PATH,
        sizes=[(256, 256), (128, 128), (96, 96), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Saved {PNG_PATH}")
    print(f"Saved {ICO_PATH}")


if __name__ == "__main__":
    main()
