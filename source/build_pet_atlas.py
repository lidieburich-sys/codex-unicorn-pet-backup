#!/usr/bin/env python3
"""Build the Codex Unicorn desktop pet atlas from cleaned pose art."""

from __future__ import annotations

import json
import zipfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parent
CELL_W = 192
CELL_H = 208
COLS = 8
ROWS = 9

ROW_SPECS = [
    ("idle", 6),
    ("running-right", 8),
    ("running-left", 8),
    ("waving", 4),
    ("jumping", 5),
    ("failed", 8),
    ("waiting", 6),
    ("running", 6),
    ("review", 6),
]


def zero_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = np.array(rgba)
    data[data[:, :, 3] == 0, :3] = 0
    return Image.fromarray(data, "RGBA")


def alpha_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = np.array(image.getchannel("A"))
    ys, xs = np.where(alpha > threshold)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def connected_components(mask: np.ndarray) -> list[tuple[int, tuple[int, int, int, int], list[tuple[int, int]]]]:
    height, width = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    components: list[tuple[int, tuple[int, int, int, int], list[tuple[int, int]]]] = []

    for start_y in range(height):
        candidates = np.where(mask[start_y] & ~seen[start_y])[0]
        for start_x in candidates:
            if seen[start_y, start_x] or not mask[start_y, start_x]:
                continue
            queue: deque[tuple[int, int]] = deque([(int(start_x), int(start_y))])
            seen[start_y, start_x] = True
            pixels: list[tuple[int, int]] = []
            min_x = max_x = int(start_x)
            min_y = max_y = int(start_y)

            while queue:
                x, y = queue.popleft()
                pixels.append((x, y))
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                for nx, ny in (
                    (x + 1, y),
                    (x - 1, y),
                    (x, y + 1),
                    (x, y - 1),
                    (x + 1, y + 1),
                    (x - 1, y - 1),
                    (x + 1, y - 1),
                    (x - 1, y + 1),
                ):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((nx, ny))

            components.append((len(pixels), (min_x, min_y, max_x + 1, max_y + 1), pixels))

    components.sort(key=lambda item: item[0], reverse=True)
    return components


def clean_pose(path: str, keep: str = "largest") -> Image.Image:
    image = Image.open(ROOT / path).convert("RGBA")
    alpha = np.array(image.getchannel("A"))
    components = connected_components(alpha > 18)
    if not components:
        return Image.new("RGBA", image.size)

    keep_pixels: set[tuple[int, int]] = set()
    if keep == "failed":
        largest = components[0][0]
        for count, _bbox, pixels in components:
            if count == largest or count >= 2500:
                keep_pixels.update(pixels)
    else:
        keep_pixels.update(components[0][2])

    keep_mask = np.zeros(alpha.shape, dtype=bool)
    for x, y in keep_pixels:
        keep_mask[y, x] = True

    data = np.array(image)
    data[~keep_mask, 3] = 0
    data[data[:, :, 3] == 0, :3] = 0
    cleaned = Image.fromarray(data, "RGBA")
    bbox = alpha_bbox(cleaned)
    if bbox is None:
        return cleaned
    left, top, right, bottom = bbox
    pad = 6
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(cleaned.width, right + pad)
    bottom = min(cleaned.height, bottom + pad)
    return zero_transparent_rgb(cleaned.crop((left, top, right, bottom)))


def resize_contain(image: Image.Image, max_w: int, max_h: int, scale: float = 1.0) -> Image.Image:
    factor = min(max_w / image.width, max_h / image.height) * scale
    width = max(1, round(image.width * factor))
    height = max(1, round(image.height * factor))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def transformed(
    image: Image.Image,
    max_w: int,
    max_h: int,
    *,
    scale: float = 1.0,
    sx: float = 1.0,
    sy: float = 1.0,
    rotate: float = 0.0,
    flip: bool = False,
) -> Image.Image:
    sprite = ImageOps.mirror(image) if flip else image
    sprite = resize_contain(sprite, max_w, max_h, scale)
    if sx != 1.0 or sy != 1.0:
        sprite = sprite.resize(
            (max(1, round(sprite.width * sx)), max(1, round(sprite.height * sy))),
            Image.Resampling.LANCZOS,
        )
    if rotate:
        sprite = sprite.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
    return zero_transparent_rgb(sprite)


def compose_cell(
    image: Image.Image,
    max_w: int,
    max_h: int,
    *,
    scale: float = 1.0,
    sx: float = 1.0,
    sy: float = 1.0,
    rotate: float = 0.0,
    flip: bool = False,
    center_x: float = CELL_W / 2,
    bottom: float = 200,
    x: float = 0,
    y: float = 0,
) -> Image.Image:
    sprite = transformed(image, max_w, max_h, scale=scale, sx=sx, sy=sy, rotate=rotate, flip=flip)
    cell = Image.new("RGBA", (CELL_W, CELL_H))
    paste_x = round(center_x - sprite.width / 2 + x)
    paste_y = round(bottom - sprite.height + y)
    paste_x = max(4, min(CELL_W - sprite.width - 4, paste_x))
    paste_y = max(2, min(CELL_H - sprite.height - 2, paste_y))
    cell.alpha_composite(sprite, (paste_x, paste_y))
    return zero_transparent_rgb(cell)


def make_frames() -> list[list[Image.Image]]:
    idle = clean_pose("pose-idle.png")
    run = clean_pose("pose-run.png")
    wave = clean_pose("pose-wave.png")
    jump = clean_pose("pose-jump.png")
    failed = clean_pose("pose-failed.png", keep="failed")
    sitting = clean_pose("pose-sitting.png")
    sleeping = clean_pose("pose-sleeping.png")
    coding = clean_pose("pose-coding.png")

    frames: list[list[Image.Image]] = []

    idle_motion = [(0, 0, 1.0, 1.0), (0, -2, 1.01, 0.99), (1, -3, 1.0, 1.0), (0, -2, 0.99, 1.01), (0, 1, 1.0, 1.0), (-1, 0, 1.0, 1.0)]
    frames.append([
        compose_cell(idle, 158, 184, bottom=200, x=dx, y=dy, sx=sx, sy=sy)
        for dx, dy, sx, sy in idle_motion
    ])

    run_motion = [
        (-3, 0, -2.0, 1.04, 0.96),
        (0, -3, -1.0, 0.98, 1.03),
        (3, -5, 1.0, 1.00, 1.00),
        (1, -3, 2.0, 1.03, 0.97),
        (-2, 0, 1.0, 1.04, 0.96),
        (0, -2, -1.0, 0.99, 1.02),
        (2, -4, -2.0, 1.00, 1.00),
        (0, -2, 1.0, 1.02, 0.98),
    ]
    frames.append([
        compose_cell(run, 168, 154, bottom=196, x=dx, y=dy, rotate=rot, sx=sx, sy=sy)
        for dx, dy, rot, sx, sy in run_motion
    ])
    frames.append([
        compose_cell(run, 168, 154, bottom=196, x=-dx, y=dy, rotate=-rot, sx=sx, sy=sy, flip=True)
        for dx, dy, rot, sx, sy in run_motion
    ])

    wave_motion = [(-1, 0, -1.5), (1, -3, 1.5), (0, -1, -1.0), (2, -4, 2.0)]
    frames.append([
        compose_cell(wave, 158, 184, bottom=202, x=dx, y=dy, rotate=rot)
        for dx, dy, rot in wave_motion
    ])

    jump_motion = [
        (0, 0, 1.05, 0.96, 0.0),
        (0, -20, 0.98, 1.03, -3.0),
        (0, -34, 1.00, 1.00, 0.0),
        (0, -18, 0.99, 1.02, 3.0),
        (0, 1, 1.06, 0.95, 0.0),
    ]
    frames.append([
        compose_cell(jump, 160, 176, bottom=202, x=dx, y=dy, sx=sx, sy=sy, rotate=rot)
        for dx, dy, sx, sy, rot in jump_motion
    ])

    failed_motion = [(0, 0), (0, 1), (-1, 1), (1, 2), (0, 1), (0, 0), (-1, 1), (0, 0)]
    frames.append([
        compose_cell(failed, 176, 186, bottom=202, x=dx, y=dy)
        for dx, dy in failed_motion
    ])

    sleep_motion = [(0, 0, 1.0, 1.0), (0, 1, 1.01, 0.99), (0, 2, 1.02, 0.98), (0, 1, 1.01, 0.99), (0, 0, 1.0, 1.0), (0, -1, 0.99, 1.01)]
    frames.append([
        compose_cell(sleeping, 180, 142, bottom=198, x=dx, y=dy, sx=sx, sy=sy)
        for dx, dy, sx, sy in sleep_motion
    ])

    coding_motion = [(0, 0, -1.0), (1, -1, 0.5), (0, -2, 1.0), (-1, -1, 0.0), (0, 1, -0.5), (1, 0, 0.5)]
    frames.append([
        compose_cell(coding, 180, 154, bottom=198, x=dx, y=dy, rotate=rot)
        for dx, dy, rot in coding_motion
    ])

    review_motion = [(0, 0, 0.0), (0, -1, -0.5), (1, -2, 0.8), (0, -1, 0.4), (-1, 0, -0.8), (0, 0, 0.0)]
    frames.append([
        compose_cell(coding, 178, 152, bottom=198, x=dx, y=dy, rotate=rot)
        for dx, dy, rot in review_motion
    ])

    # Keep a polished sitting pose around for manual preview and future remapping.
    compose_cell(sitting, 158, 184, bottom=202).save(ROOT / "preview-sitting-clean.png")
    return frames


def build_atlas(frames: list[list[Image.Image]]) -> Image.Image:
    atlas = Image.new("RGBA", (COLS * CELL_W, ROWS * CELL_H))
    for row, row_frames in enumerate(frames):
        for col, frame in enumerate(row_frames):
            atlas.alpha_composite(frame, (col * CELL_W, row * CELL_H))
    return zero_transparent_rgb(atlas)


def make_contact_sheet(frames: list[list[Image.Image]]) -> Image.Image:
    scale = 0.72
    label_h = 20
    gap = 8
    thumb_w = round(CELL_W * scale)
    thumb_h = round(CELL_H * scale)
    width = COLS * thumb_w + (COLS + 1) * gap
    height = ROWS * (thumb_h + label_h) + (ROWS + 1) * gap
    sheet = Image.new("RGB", (width, height), (42, 43, 58))
    draw = ImageDraw.Draw(sheet)
    for row, (name, _count) in enumerate(ROW_SPECS):
        y = gap + row * (thumb_h + label_h + gap)
        draw.text((gap, y), name, fill=(228, 224, 245))
        for col in range(COLS):
            x = gap + col * (thumb_w + gap)
            yy = y + label_h
            draw.rectangle((x, yy, x + thumb_w - 1, yy + thumb_h - 1), outline=(90, 91, 113))
            if col < len(frames[row]):
                thumb = frames[row][col].resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(thumb, (x, yy), thumb)
    return sheet


def make_gif(name: str, row: list[Image.Image], duration: int = 110) -> None:
    bg_color = (64, 65, 83)
    rendered = []
    for frame in row:
        bg = Image.new("RGBA", frame.size, bg_color + (255,))
        bg.alpha_composite(frame)
        rendered.append(bg.convert("P", palette=Image.Palette.ADAPTIVE, colors=96))
    rendered[0].save(
        ROOT / f"preview-{name}.gif",
        save_all=True,
        append_images=rendered[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )


def main() -> None:
    for old_preview in ROOT.glob("preview-*.gif"):
        old_preview.unlink()

    frames = make_frames()
    atlas = build_atlas(frames)
    atlas.save(ROOT / "spritesheet.png")
    atlas.save(ROOT / "spritesheet.webp", lossless=True, quality=100, method=6, exact=True)
    make_contact_sheet(frames).save(ROOT / "contact-sheet.png")

    preview = Image.new("RGBA", (192, 208), (64, 65, 83, 255))
    preview.alpha_composite(frames[0][0])
    preview.convert("RGB").save(ROOT / "preview-on-dark.png")
    frames[0][0].save(ROOT / "preview.png")
    frames[0][0].save(ROOT / "preview.webp", lossless=True, quality=100)

    preview_names = [
        "idle",
        "run-right",
        "run-left",
        "wave",
        "jump",
        "failed",
        "sleeping",
        "coding",
        "review",
    ]
    for index, name in enumerate(preview_names):
        make_gif(name, frames[index])

    pet_json = {
        "id": "codex-unicorn",
        "displayName": "Codex Unicorn",
        "description": "A smooth pastel coding companion with idle, run, wave, sleep, code, review, and failed states.",
        "spritesheetPath": "spritesheet.webp",
    }
    (ROOT / "pet.json").write_text(json.dumps(pet_json, indent=2) + "\n", encoding="utf-8")

    archive = ROOT.parent / "codex-unicorn-pet.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.write(ROOT / "pet.json", "pet.json")
        zipped.write(ROOT / "spritesheet.webp", "spritesheet.webp")


if __name__ == "__main__":
    main()
