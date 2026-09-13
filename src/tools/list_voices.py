"""Print the available Edge neural voices, to pick a value for TTS_VOICE.

    python -m src.tools.list_voices          # English voices
    python -m src.tools.list_voices en-GB    # filter by locale prefix
"""

from __future__ import annotations

import asyncio
import sys

import edge_tts


async def _main(locale_prefix: str) -> None:
    voices = await edge_tts.list_voices()
    matches = sorted(
        (v for v in voices if v["Locale"].startswith(locale_prefix)),
        key=lambda v: v["ShortName"],
    )
    for v in matches:
        personalities = ", ".join(v.get("VoiceTag", {}).get("VoicePersonalities", []))
        print(f"{v['ShortName']:<40} {v['Gender']:<8} {personalities}")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1] if len(sys.argv) > 1 else "en-"))
