import requests
from PIL.Image import Image

from postautomation.uploader import Uploader


class CatboxUploader(Uploader):
    api_base = "https://catbox.moe/user/api.php"

    def upload(self, url: str, image: Image) -> str:
        mime, b = self._get_bytes(image)

        result = requests.post(self.api_base, data={
            "reqtype": "fileupload",
        }, files={
            "fileToUpload": (f"image.{mime.split('/')[1]}", b, mime)
        })

        content = result.content.decode("utf-8")
        if not content.startswith("http"):
            raise OSError(content)
        print(f"Image uploaded @ {content}")
        return content
