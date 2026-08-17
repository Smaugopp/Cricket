from pathlib import Path
import os

class MediaService:
    def __init__(self):
        self.banner = Path("assets/start_banner.jpg")
        self.live_gif = Path("assets/cricket_live.gif")
        self.start_video_file_id = os.getenv("START_VIDEO_FILE_ID", "").strip()

    def has_banner(self):
        return self.banner.exists()

    def has_gif(self):
        return self.live_gif.exists()
