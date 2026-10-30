"""Image pixels and original JPEG streams to PDF; no UI dependencies."""

import io, shutil
from PIL import Image
import fitz
from image_inputs import frames
from bakuri.domain.formats import IMAGES
from .office import office


def to_pdf(src, dest, session=None, control=None, advance=lambda f: None):
    ext = src.suffix.lower()
    if ext == ".pdf":
        shutil.copyfile(src, dest)
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
            document.save(dest, garbage=4, deflate=True, deflate_images=True)
    else:
        (session.export if session else office)(src, dest, "PDF")
