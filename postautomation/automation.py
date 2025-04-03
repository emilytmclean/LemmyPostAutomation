import traceback
from datetime import datetime
from io import BytesIO
from time import sleep
from typing import List, Optional

import requests
from PIL import Image
from croniter import croniter
from pythonlemmy import LemmyHttp
from pythonlemmy.responses import GetCommunityResponse

from postautomation import PostCandidate, PostData
from postautomation.candidate import CandidateProvider, CSVCandidateProvider
from postautomation.handlers.base import Handler
from postautomation.handlers.e621_handler import E621Handler
from postautomation.handlers.furaffinity_handler import FuraffinityHandler
from postautomation.monitor import PostMonitor
from postautomation.reconnection_manager import ReconnectionDelayManager
from postautomation.scraper import Scraper
from postautomation.uploader import Uploader, CatboxUploader


class PostAutomation:
    lemmy: LemmyHttp
    community_id: int
    monitor: PostMonitor
    scraper: Scraper
    candidate_provider: CandidateProvider
    cron: Optional[croniter]
    uploader: Uploader
    reconnection_manager = ReconnectionDelayManager()
    mock: bool

    def __init__(
            self,
            lemmy: LemmyHttp,
            community_name: str, monitor:
            PostMonitor,
            scraper: Scraper,
            candidate_provider: CandidateProvider,
            uploader: Uploader,
            cron: Optional[str],
            mock: bool = False
    ):
        self.lemmy = lemmy
        self.community_id = GetCommunityResponse(lemmy.get_community(name=community_name)).community_view.community.id
        self.monitor = monitor
        self.scraper = scraper
        self.candidate_provider = candidate_provider
        self.uploader = uploader
        self.mock = mock
        if cron is not None:
            self.cron = croniter(cron, datetime.now())

    @staticmethod
    def create(
        lemmy: LemmyHttp,
        community_name: str,
        csv_file_location: str,
        cron: Optional[str] = None,
        handlers: Optional[List[Handler]] = None,
        uploader: Uploader = CatboxUploader()
    ):
        return PostAutomation(
            lemmy,
            community_name,
            PostMonitor(community_name, lemmy),
            Scraper([E621Handler(), FuraffinityHandler()] if handlers is None else handlers),
            CSVCandidateProvider(csv_file_location),
            uploader,
            cron
        )

    def run(self):
        if self.cron is None:
            print("No cron found, exiting...")
            return

        print("Updating database")
        self.monitor.update_database()

        while True:
            next_run: datetime = self.cron.get_next(datetime, datetime.now())
            sleep_time = (next_run - datetime.now()).total_seconds()
            print(f"Sleeping for {sleep_time} (until {next_run})")
            if sleep_time > 0:
                sleep(sleep_time)
            self.candidate_provider.refresh_candidates()
            self.run_once()

    def run_once(self):
        while True:
            try:
                self._run_once()
                self.reconnection_manager.reset()
                break
            except Exception:
                print(traceback.format_exc())
                self.reconnection_manager.wait()

    def _run_once(self):
        print("Updating database")
        self.monitor.update_database()

        print("Finding a candidate for a post")
        candidates: List[PostCandidate] = self.candidate_provider.list_candidates(None)[0]
        chosen: Optional[PostData] = None
        chosen_candidate: Optional[PostCandidate] = None
        chosen_image: Optional[Image] = None
        for candidate in candidates:
            scraped = self.scraper.scrape(candidate.url)
            image = Image.open(BytesIO(requests.get(scraped.image_url).content))
            
            if not self.monitor.has_been_posted(image):
                if candidate.title is not None:
                    scraped.title = candidate.title
                elif scraped.title is None:
                    print(f"Candidate {scraped.url} does not have a title")
                    continue

                if candidate.content_warnings is not None:
                    scraped.content_warnings = candidate.content_warnings

                chosen = scraped
                chosen_candidate = candidate
                chosen_image = image
                break
            else:
                self.candidate_provider.remove_candidate(candidate, True)

        if chosen is None:
            print("No candidates found")
            return

        print("Candidate found")
        print(f"Candidate url: {chosen_candidate.url}")
        print(f"Candidate title: {chosen_candidate.title}")
        print(f"Candidate content warnings: {chosen_candidate.content_warnings}")
        print("Uploading image")
        if not self.mock:
            try:
                image_url = self.uploader.upload(chosen.image_url, chosen_image)
            except Exception:
                print(traceback.format_exc())
                image_url = chosen.image_url

        content_warning = ""
        if chosen.content_warnings is not None and len(chosen.content_warnings) > 0:
            content_warning = "[" + ", ".join(chosen.content_warnings) + "] "
        title = f"{chosen.title} {content_warning}({', '.join(chosen.artists)})"
        body = f"[Source]({chosen.url})"

        print(f"Creating post with title \"{title}\" and body \"{body}\"")

        if not self.mock:
            response = self.lemmy.create_post(
                title,
                self.community_id,
                body=body,
                nsfw=chosen.nsfw,
                url=image_url
            )
            if response.status_code != 200:
                print(f"Failed to create post: {response.text}")
                return
            print("Post created")
        self.candidate_provider.remove_candidate(chosen_candidate)
