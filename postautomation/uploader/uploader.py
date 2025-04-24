import io
from typing import Tuple

from PIL import Image


class Uploader:

    def _get_bytes(self, image: Image.Image) -> Tuple[str, bytes]:
        b = io.BytesIO()
        image.save(b, image.format)
        mime = Image.MIME.get(image.format)

        return mime, b.getvalue()

    def upload(self, url: str, image: Image.Image) -> str:
        pass
