import json
from typing import Optional

import requests
from PIL.Image import Image

from postautomation.uploader import Uploader


class PictrsUploader(Uploader):

    def __init__(
            self,
            instance_url: str,
            jwt: Optional[str] = None
    ):
        if not instance_url.startswith("http://") and not instance_url.startswith("https://"):
            instance_url = "https://" + instance_url
        if instance_url.endswith("/"):
            instance_url = instance_url[:-1]
        self.instance_url = instance_url
        self.jwt = jwt

    def upload(self, url: str, image: Image) -> str:
        mime, b = self._get_bytes(image)

        result = requests.post(f"{self.instance_url}/pictrs/image", files={
            "images[]": (f"image.{mime.split('/')[1]}", b, mime)
        }, cookies={"jwt": self.jwt})

        content_s = result.content.decode("utf-8")
        content = json.loads(content_s)

        print(content_s)
        if "error" in content:
            raise OSError(content_s)

        delete_token = content["files"][0]["delete_token"]
        image_url = f"{self.instance_url}/pictrs/image/{content['files'][0]['file']}"

        print(f"Image uploaded @ {image_url} (delete_token: {delete_token})")
        return image_url
