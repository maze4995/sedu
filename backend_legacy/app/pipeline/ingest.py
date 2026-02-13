"""PDF → page images using pypdfium2."""

from __future__ import annotations

from PIL import Image


def render_pdf_to_images(
    pdf_bytes: bytes,
    *,
    dpi: int = 250,
) -> list[Image.Image]:
    """Render every page of a PDF to a PIL Image at the given DPI.

    Args:
        pdf_bytes: Raw PDF file content.
        dpi: Resolution for rasterisation (default 250, good balance
             between OCR quality and speed).

    Returns:
        List of PIL RGB Images, one per page.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "pypdfium2 is required for PDF rendering. "
            "Install it with: pip install pypdfium2"
        ) from exc

    scale = dpi / 72  # pypdfium2 default is 72 dpi

    pdf = pdfium.PdfDocument(pdf_bytes)
    images: list[Image.Image] = []

    try:
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil().convert("RGB")
            images.append(img)
    finally:
        pdf.close()

    return images
