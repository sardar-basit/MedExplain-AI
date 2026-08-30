"""Generate synthetic lab-report fixtures for OCR quality checks.

These are NOT real patient reports — they exist so we can judge line/value
alignment before real samples are provided.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent


def _font(size: int) -> ImageFont.ImageFont:
    for name in (
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        path = Path(name)
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def write_report(
    path: Path,
    *,
    title: str,
    subtitle: str,
    rows: list[tuple[str, str, str, str]],
    bg: tuple[int, int, int],
) -> None:
    img = Image.new("RGB", (1000, 160 + 36 * (len(rows) + 2)), color=bg)
    draw = ImageDraw.Draw(img)
    title_font = _font(30)
    meta_font = _font(16)
    body_font = _font(18)

    draw.text((40, 28), title, fill=(10, 74, 76), font=title_font)
    draw.text((40, 72), subtitle, fill=(80, 100, 105), font=meta_font)

    # Fixed-width style columns for clearer OCR (monospace preferred).
    y = 120
    headers = f"{'Test':<22} {'Result':>8} {'Unit':<12} {'Reference':<14}"
    draw.text((40, y), headers, fill=(15, 107, 109), font=body_font)
    y += 28
    draw.line((40, y, 960, y), fill=(180, 200, 198), width=2)
    y += 14
    for marker, value, unit, ref in rows:
        line = f"{marker:<22} {value:>8} {unit:<12} {ref:<14}"
        draw.text((40, y), line, fill=(20, 50, 58), font=body_font)
        y += 32

    img.save(path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_report(
        OUT_DIR / "lab_cbc.png",
        title="City Lab - Complete Blood Count",
        subtitle="Sample ID: SYN-CBC-001   Collected: 2026-08-20",
        rows=[
            ("Hemoglobin", "11.8", "g/dL", "12.0-16.0"),
            ("Hematocrit", "36.2", "%", "36.0-46.0"),
            ("WBC", "7.2", "10^3/uL", "4.0-11.0"),
            ("RBC", "4.1", "10^6/uL", "4.0-5.2"),
            ("Platelets", "420", "10^3/uL", "150-400"),
            ("MCV", "88", "fL", "80-100"),
        ],
        bg=(244, 250, 249),
    )
    write_report(
        OUT_DIR / "lab_cmp.png",
        title="Metabolic Panel (CMP)",
        subtitle="Patient: Demo Only - Educational Fixture",
        rows=[
            ("Glucose", "118", "mg/dL", "70-99"),
            ("Creatinine", "0.9", "mg/dL", "0.6-1.3"),
            ("BUN", "18", "mg/dL", "7-20"),
            ("Sodium", "139", "mmol/L", "136-145"),
            ("Potassium", "4.2", "mmol/L", "3.5-5.1"),
            ("ALT", "42", "U/L", "7-56"),
            ("AST", "38", "U/L", "10-40"),
        ],
        bg=(250, 248, 244),
    )
    write_report(
        OUT_DIR / "lab_lipid.png",
        title="Lipid Profile Report",
        subtitle="Fixture SYN-LIPID-003",
        rows=[
            ("Total Cholesterol", "212", "mg/dL", "<200"),
            ("LDL Cholesterol", "138", "mg/dL", "<100"),
            ("HDL Cholesterol", "44", "mg/dL", ">40"),
            ("Triglycerides", "165", "mg/dL", "<150"),
            ("Non-HDL", "168", "mg/dL", "<130"),
        ],
        bg=(245, 247, 250),
    )
    print(f"Wrote fixtures to {OUT_DIR}")


if __name__ == "__main__":
    main()
