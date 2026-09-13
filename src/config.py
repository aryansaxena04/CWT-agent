"""Central place to load and validate required environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
ADS_DIR = DATA_DIR / "ads"
SCRIPTS_DIR = DATA_DIR / "scripts"
PROPRIETARY_DIR = DATA_DIR / "proprietary"
OUTPUT_VIDEOS_DIR = ROOT / "output" / "videos"

for d in (ADS_DIR, SCRIPTS_DIR, PROPRIETARY_DIR, OUTPUT_VIDEOS_DIR):
    d.mkdir(parents=True, exist_ok=True)


class Settings:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")

    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
    APIFY_META_ADS_ACTOR: str = os.getenv("APIFY_META_ADS_ACTOR", "curious_coder/facebook-ads-library-scraper")

    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    EXA_API_KEY: str = os.getenv("EXA_API_KEY", "")

    PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "")

    # Microsoft Edge's neural voices, via edge-tts: free, no API key, and far
    # more natural than gTTS. Slight rate boost gives it ad-read energy.
    TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-AndrewNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+8%")
    TTS_PITCH: str = os.getenv("TTS_PITCH", "-2Hz")

    OPENMONTAGE_PATH: str = os.getenv("OPENMONTAGE_PATH", "")

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n, "")]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                f"Copy .env.example to .env and fill them in."
            )


settings = Settings()
