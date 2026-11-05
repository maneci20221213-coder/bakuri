"""Image pixels and original JPEG streams to PDF; no UI dependencies."""

import io, shutil
from PIL import Image
import fitz
from image_inputs import frames
from bakuri.domain.formats import CAD, IMAGES
from .office import office


def jpeg_pdf(src, dest, control=None, orientation="auto"):
    """Embed the original JPEG stream; express EXIF orientation in PDF geometry."""
    with Image.open(src) as image:
        if image.format not in {"JPEG", "MPO"}:
            return False
        width, height = image.size
        exif_orientation = image.getexif().get(274, 1)
    if exif_orientation in {5, 6, 7, 8}:
        width, height = height, width
    width, height = width * 72 / 150, height * 72 / 150
    if control:
        control.check()
    with fitz.open() as document:
        page = document.new_page(width=width, height=height)
        page.insert_image(page.rect, filename=str(src), keep_proportion=False)
        matrices = {
            2: (-width, 0, 0, height, width, 0),
            3: (-width, 0, 0, -height, width, height),
            4: (width, 0, 0, -height, 0, height),
            5: (0, -height, -width, 0, width, height),
            6: (0, -height, width, 0, 0, height),
            7: (0, height, width, 0, 0, 0),
            8: (0, height, -width, 0, width, 0),
        }
        if exif_orientation in matrices:
            matrix = " ".join(str(value) for value in matrices[exif_orientation])
            name = page.get_images()[0][7]
            document.update_stream(page.get_contents()[0], f"q {matrix} cm /{name} Do Q".encode())
        if control:
            control.check()
        save_image_pdf(document, dest, orientation)
    return True


def save_image_pdf(document, dest, orientation):
    if orientation == "auto":
        document.save(dest, garbage=4, deflate=True, deflate_images=True)
        return
    paper = fitz.paper_rect("a4-l" if orientation == "landscape" else "a4")
    with fitz.open() as output:
        for index in range(len(document)):
            page = output.new_page(width=paper.width, height=paper.height)
            page.show_pdf_page(page.rect, document, index)
        output.save(dest, garbage=4, deflate=True, deflate_images=True)


def to_pdf(src, dest, session=None, control=None, advance=lambda f: None, *, orientation="auto"):
    ext = src.suffix.lower()
    if ext == ".pdf":
        shutil.copyfile(src, dest)
    elif ext in {".jpg", ".jpeg"} and jpeg_pdf(src, dest, control, orientation):
        advance(0.8)
    elif ext in CAD:
        from .cad import cad_to_pdf

        cad_to_pdf(src, dest, control, advance, orientation)
    elif ext in IMAGES:
        with fitz.open() as document:
            for index, image in enumerate(frames(src)):
                if control:
                    control.check()
                page = document.new_page(
                    width=image.width * 72 / 150, height=image.height * 72 / 150
                )
                original_jpeg = False
                if ext in {".jpg", ".jpeg"}:
                    with Image.open(src) as original:
                        original_jpeg = original.getexif().get(274, 1) == 1
                if original_jpeg:
                    page.insert_image(page.rect, filename=str(src))
                else:
                    if image.getchannel("A").getextrema() == (255, 255):
                        image = image.convert("RGB")
                    if image.mode == "RGB":
                        pixmap = fitz.Pixmap(
                            fitz.csRGB, image.width, image.height, image.tobytes(), False
                        )
                        page.insert_image(page.rect, pixmap=pixmap)
                    else:
                        # PNG decoding handles straight-alpha premultiplication correctly.
                        data = io.BytesIO()
                        image.save(data, "PNG", compress_level=1)
                        page.insert_image(page.rect, stream=data.getvalue())
                advance(0.25 + 0.5 * (index + 1) / (index + 2))
            if control:
                control.check()
            save_image_pdf(document, dest, orientation)
    else:
        (session.export if session else office)(src, dest, "PDF")
