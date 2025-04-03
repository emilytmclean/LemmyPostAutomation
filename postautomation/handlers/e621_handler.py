from bs4 import BeautifulSoup

from postautomation import PostData
from postautomation.handlers.base import Handler


class E621Handler(Handler):
    def supports_domain(self, domain: str) -> bool:
        return domain == "e621.net"

    def scrape(self, url: str, document: BeautifulSoup) -> PostData:
        artists = list(
            filter(lambda x: x != "conditional dnp", [
                x.find("span").find(text=True).strip().replace(" (artist)", "") for x in document.find_all(
                    "a",
                    {"itemprop": "author"},
                )
            ])
        )
        print(artists)
        img_url = document.find(
            "section", {"id": "image-container"},
        )["data-file-url"]

        nsfw = document.find("span", {"id": "post-rating-text"}).getText().strip() != "Safe"

        return PostData(
            url,
            None,
            artists,
            img_url,
            nsfw
        )