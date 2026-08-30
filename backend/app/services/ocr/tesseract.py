"""Tesseract OCR implementation (local / dev default)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.ocr.base import OCRResult, OCRService
from app.services.ocr.file_loader import resolve_local_path

# Camera photos of full pages are often <800px wide; Tesseract needs more pixels.
_MIN_OCR_WIDTH = 1600
_MAX_OCR_WIDTH = 2400


def _configure_tesseract_cmd(settings: Settings) -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        return

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


def _open_images(path: Path) -> list[Image.Image]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pdf = pdfium.PdfDocument(str(path))
        images: list[Image.Image] = []
        for index in range(min(len(pdf), 5)):
            page = pdf[index]
            bitmap = page.render(scale=2.0)
            images.append(bitmap.to_pil())
        if not images:
            raise AppError(
                code="ocr_empty_pdf",
                message="PDF has no pages to OCR.",
                status_code=400,
            )
        return images

    if suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(path) as img:
            return [ImageOps.exif_transpose(img.convert("RGB"))]

    raise AppError(
        code="ocr_unsupported_type",
        message="OCR supports PDF, JPG, and PNG only.",
        status_code=400,
    )


def _upscale_for_ocr(image: Image.Image) -> Image.Image:
    """Upscale small phone photos so glyph strokes are thick enough for Tesseract."""
    width, height = image.size
    if width >= _MIN_OCR_WIDTH:
        if width > _MAX_OCR_WIDTH:
            scale = _MAX_OCR_WIDTH / width
            return image.resize(
                (int(width * scale), int(height * scale)),
                Image.Resampling.LANCZOS,
            )
        return image
    scale = min(_MAX_OCR_WIDTH / width, max(2.0, _MIN_OCR_WIDTH / width))
    return image.resize(
        (int(width * scale), int(height * scale)),
        Image.Resampling.LANCZOS,
    )


def _preprocess_variants(image: Image.Image) -> list[Image.Image]:
    """Produce a few enhanced variants; phone photos often need binarization."""
    base = _upscale_for_ocr(ImageOps.exif_transpose(image.convert("RGB")))
    gray = ImageOps.grayscale(base)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.5)
    gray = ImageEnhance.Sharpness(gray).enhance(1.8)
    gray = gray.filter(ImageFilter.SHARPEN)

    # Mild threshold helps creased / shadowed paper under uneven light.
    bw = gray.point(lambda pixel: 255 if pixel > 155 else 0)
    return [gray, bw]


def _ocr_plain(image: Image.Image) -> str:
    chunks: list[str] = []
    for psm in (4, 6):
        text = pytesseract.image_to_string(
            image,
            config=f"--oem 3 --psm {psm}",
        ).strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _merge_ocr_texts(*texts: str) -> str:
    """Keep unique lines (order preserved) so fragile tokens survive across variants."""
    seen: set[str] = set()
    ordered: list[str] = []
    for text in texts:
        for line in text.splitlines():
            cleaned = " ".join(line.split())
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            ordered.append(cleaned)
    return "\n".join(ordered).strip()


def _lines_from_ocr_data(image: Image.Image) -> str:
    """Rebuild line-oriented text so test / value / unit stay roughly aligned.

    Tesseract often splits table columns into different blocks. We cluster words
    by vertical position (top) into rows, then sort left-to-right within each row.
    """
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words: list[tuple[int, int, str]] = []  # (top, left, text)
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        words.append((int(data["top"][i]), int(data["left"][i]), text))

    if not words:
        return ""

    words.sort(key=lambda item: (item[0], item[1]))
    heights = [
        max(8, abs(data["height"][i]))
        for i in range(n)
        if (data["text"][i] or "").strip()
    ]
    row_tol = max(10, int((sorted(heights)[len(heights) // 2] if heights else 16) * 0.6))

    rows: list[list[tuple[int, str]]] = []
    current_top: int | None = None
    current_row: list[tuple[int, str]] = []
    for top, left, text in words:
        if current_top is None or abs(top - current_top) <= row_tol:
            if current_top is None:
                current_top = top
            current_row.append((left, text))
        else:
            rows.append(current_row)
            current_row = [(left, text)]
            current_top = top
    if current_row:
        rows.append(current_row)

    ordered: list[str] = []
    for row in rows:
        row.sort(key=lambda item: item[0])
        ordered.append(" ".join(text for _, text in row))
    return "\n".join(ordered).strip()


def _extract_sync(path: Path, settings: Settings | None = None) -> str:
    _configure_tesseract_cmd(settings or get_settings())
    images = _open_images(path)
    page_texts: list[str] = []
    try:
        for index, image in enumerate(images, start=1):
            variant_texts: list[str] = []
            for variant in _preprocess_variants(image):
                try:
                    line_text = _lines_from_ocr_data(variant)
                    plain = _ocr_plain(variant)
                    variant_texts.append(_merge_ocr_texts(line_text, plain))
                finally:
                    variant.close()
            page_text = _merge_ocr_texts(*variant_texts)
            if page_text:
                if index > 1:
                    page_texts.append(f"--- page {index} ---")
                page_texts.append(page_text)
    finally:
        for image in images:
            image.close()

    text = "\n".join(page_texts).strip()
    if not text:
        raise AppError(
            code="ocr_empty_result",
            message="OCR produced no readable text from this file.",
            status_code=422,
        )
    return text


class TesseractOCRService(OCRService):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        _configure_tesseract_cmd(self._settings)

    async def extract(self, file_url: str) -> OCRResult:
        path = resolve_local_path(file_url, self._settings)

        def _run() -> str:
            try:
                return _extract_sync(path)
            except pytesseract.TesseractNotFoundError as exc:
                raise AppError(
                    code="tesseract_not_found",
                    message=(
                        "Tesseract binary not found. Install Tesseract OCR and set "
                        "TESSERACT_CMD if it is not on PATH."
                    ),
                    status_code=500,
                ) from exc
            except AppError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise AppError(
                    code="ocr_failed",
                    message="Tesseract OCR failed while reading the uploaded file.",
                    status_code=500,
                ) from exc

        raw_text = await asyncio.to_thread(_run)
        return OCRResult(raw_text=raw_text)
