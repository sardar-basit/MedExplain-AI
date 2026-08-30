"""Build PNG + PDF lab fixtures for QA."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from generate_lab_fixtures import main as generate_pngs

OUT = Path(__file__).resolve().parent


def png_to_pdf(png: Path, pdf: Path) -> None:
    img = Image.open(png).convert("RGB")
    img.save(pdf, "PDF", resolution=150.0)


def main() -> None:
    generate_pngs()
    for name in ("lab_cbc", "lab_cmp", "lab_lipid"):
        png = OUT / f"{name}.png"
        pdf = OUT / f"{name}.pdf"
        png_to_pdf(png, pdf)
        print(f"wrote {pdf.name}")

    # Negative control: tiny blank image → OCR/parsing should fail gracefully.
    blank = Image.new("RGB", (80, 40), color=(255, 255, 255))
    blank.save(OUT / "sample-report.png")
    print("wrote sample-report.png")


if __name__ == "__main__":
    main()
