"""Video rendering: two renderers behind one interface.

1. OpenMontageRenderer - the assignment's preferred tool
   (https://github.com/calesthio/OpenMontage). OpenMontage is itself an
   agent-orchestrated system (YAML pipeline manifests + a Python tool
   registry, meant to be driven by an AI coding assistant) rather than a
   library with a stable public API/CLI. This adapter writes our VideoScript
   out as an OpenMontage-style scene manifest and shells out to it. Clone
   OpenMontage, set OPENMONTAGE_PATH to it, and re-check
   `pipeline_defs/` + `tools/tool_registry.py` in that checkout before
   trusting the manifest shape below verbatim — it's written from
   OpenMontage's documented conventions, not a schema dump.

2. FallbackFFmpegRenderer - a self-contained renderer (Pexels stock footage
   + Edge neural TTS voiceover + MoviePy assembly) that guarantees the pipeline produces
   a real MP4 end-to-end even before OpenMontage is wired up locally.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import asyncio
import textwrap

import edge_tts
import numpy as np
import requests
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

# moviepy 1.0.3 (last release supporting `from moviepy.editor import ...`)
# calls PIL's removed `Image.ANTIALIAS` constant internally; Pillow 10+ only
# has `Image.Resampling.LANCZOS` (the same filter, renamed). Shim it back in
# rather than pinning an old Pillow, which has no prebuilt wheel for
# Python 3.13.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

# moviepy's TextClip shells out to ImageMagick, which most machines (including
# the one this was built on) don't have installed. Text overlays are rendered
# with PIL directly instead, so the fallback renderer has zero external
# binary dependencies beyond the ffmpeg that imageio-ffmpeg bundles.
# A beat of silence after each line so cuts don't land on the last syllable,
# and a short dissolve between scenes instead of a hard cut.
_SCENE_TAIL_PADDING_SEC = 0.45
_CROSSFADE_SEC = 0.35

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _text_overlay_clip(text: str, duration: float, frame_size: tuple[int, int], font_size: int = 64):
    img = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)
    wrapped = textwrap.fill(text, width=22)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", stroke_width=3)
    x = (frame_size[0] - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (frame_size[1] - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.multiline_text(
        (x, y), wrapped, font=font, fill="white", stroke_width=3, stroke_fill="black", align="center"
    )
    return ImageClip(np.array(img), duration=duration)

from src.config import OUTPUT_VIDEOS_DIR, settings
from src.schemas import Scene, VideoRenderResult, VideoScript


class OpenMontageRenderer:
    def __init__(self, openmontage_path: str | None = None):
        self.path = Path(openmontage_path or settings.OPENMONTAGE_PATH)

    def available(self) -> bool:
        return self.path.exists() and (self.path / "pipeline_defs").exists()

    def render(self, script: VideoScript) -> VideoRenderResult:
        if not self.available():
            return VideoRenderResult(
                script_variant=script.variant,
                output_path="",
                duration_sec=0,
                renderer="openmontage",
                success=False,
                notes=(
                    "OPENMONTAGE_PATH not set or pipeline_defs/ missing. "
                    "Clone calesthio/OpenMontage, run its `make setup`, set "
                    "OPENMONTAGE_PATH in .env, and confirm the manifest shape "
                    "in _build_manifest() against that checkout."
                ),
            )

        manifest = self._build_manifest(script)
        manifest_path = self.path / "pipeline_defs" / f"crowdwisdom_{script.variant}.yaml"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        result = subprocess.run(
            ["make", "render", f"PROJECT={manifest_path.stem}"],
            cwd=self.path,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        expected_output = self.path / "output" / f"{manifest_path.stem}.mp4"
        success = result.returncode == 0 and expected_output.exists()

        final_path = OUTPUT_VIDEOS_DIR / f"ad_{script.variant}.mp4"
        if success:
            final_path.write_bytes(expected_output.read_bytes())

        return VideoRenderResult(
            script_variant=script.variant,
            output_path=str(final_path) if success else "",
            duration_sec=script.est_duration_sec,
            renderer="openmontage",
            success=success,
            notes="" if success else f"stdout={result.stdout[-500:]} stderr={result.stderr[-500:]}",
        )

    def _build_manifest(self, script: VideoScript) -> dict:
        return {
            "title": f"crowdwisdom_{script.variant}",
            "platform": "instagram_reels",
            "target_duration_sec": script.est_duration_sec,
            "style": "cinematic",
            "hook": script.visual_hook,
            "scenes": [
                {
                    "order": s.order,
                    "duration_sec": s.duration_sec,
                    "visual_prompt": s.visual,
                    "voiceover": s.voiceover,
                    "on_screen_text": s.on_screen_text,
                    "sfx_note": s.sfx_or_music_note,
                }
                for s in script.scenes
            ],
            "cta": script.cta,
        }


class FallbackFFmpegRenderer:
    """Guaranteed-to-run renderer: Pexels stock + Edge neural TTS + MoviePy."""

    def render(self, script: VideoScript) -> VideoRenderResult:
        settings.require("PEXELS_API_KEY")
        clips = [self._render_scene(scene) for scene in sorted(script.scenes, key=lambda s: s.order)]
        # Negative padding overlaps neighbouring scenes so crossfadein reads as a
        # dissolve between them rather than a fade up from black on each cut.
        final = concatenate_videoclips(clips, method="compose", padding=-_CROSSFADE_SEC)

        out_path = OUTPUT_VIDEOS_DIR / f"ad_{script.variant}_fallback.mp4"
        final.write_videofile(str(out_path), fps=30, codec="libx264", audio_codec="aac", logger=None)

        return VideoRenderResult(
            script_variant=script.variant,
            output_path=str(out_path),
            duration_sec=final.duration,
            renderer="fallback_ffmpeg",
            success=True,
        )

    def _render_scene(self, scene: Scene):
        # Narration drives the cut: a scene never ends before its line finishes,
        # otherwise the voiceover is chopped mid-word. The scripted duration is
        # a floor, not a ceiling.
        audio = None
        duration = scene.duration_sec
        if scene.voiceover:
            audio = AudioFileClip(str(self._synthesize_voiceover(scene.voiceover, scene.order)))
            duration = max(duration, audio.duration + _SCENE_TAIL_PADDING_SEC)

        bg_path = self._fetch_stock_clip(scene.visual)
        if bg_path:
            source = VideoFileClip(str(bg_path))
            visual = source.loop(duration=duration) if source.duration < duration else source.subclip(0, duration)
        else:
            visual = ImageClip(self._solid_frame(), duration=duration)
        visual = visual.resize(height=1920).crop(x_center=visual.w / 2, width=1080)

        layers = [visual]
        if scene.on_screen_text:
            layers.append(_text_overlay_clip(scene.on_screen_text, duration, (1080, 1920)))

        composite = CompositeVideoClip(layers, size=(1080, 1920)).set_duration(duration)
        if audio is not None:
            composite = composite.set_audio(audio)

        return composite.crossfadein(_CROSSFADE_SEC)

    def _fetch_stock_clip(self, visual_desc: str) -> Path | None:
        query = " ".join(visual_desc.split()[:6])
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": settings.PEXELS_API_KEY},
                params={"query": query, "per_page": 1, "orientation": "portrait"},
                timeout=20,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if not videos:
                return None
            files = sorted(videos[0]["video_files"], key=lambda f: f.get("width", 0), reverse=True)
            video_url = files[0]["link"]

            dest = OUTPUT_VIDEOS_DIR / f"_stock_{abs(hash(query))}.mp4"
            if not dest.exists():
                video_bytes = requests.get(video_url, timeout=60).content
                dest.write_bytes(video_bytes)
            return dest
        except Exception:
            return None

    def _solid_frame(self):
        import numpy as np

        return np.full((1920, 1080, 3), (10, 10, 20), dtype="uint8")

    def _synthesize_voiceover(self, text: str, scene_order: int) -> Path:
        dest = OUTPUT_VIDEOS_DIR / f"_vo_{scene_order}.mp3"
        try:
            asyncio.run(
                edge_tts.Communicate(
                    text,
                    voice=settings.TTS_VOICE,
                    rate=settings.TTS_RATE,
                    pitch=settings.TTS_PITCH,
                ).save(str(dest))
            )
        except Exception:
            # gTTS is markedly more robotic, but it keeps the pipeline running
            # if Edge's endpoint is unreachable (offline, blocked network).
            gTTS(text=text, lang="en").save(str(dest))
        return dest


def render_script(script: VideoScript) -> VideoRenderResult:
    """Try OpenMontage first (assignment's preferred tool); fall back to the
    self-contained renderer so the pipeline always produces an MP4."""
    om = OpenMontageRenderer()
    if om.available():
        result = om.render(script)
        if result.success:
            return result
    return FallbackFFmpegRenderer().render(script)
