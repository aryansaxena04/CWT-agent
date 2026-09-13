"""Shared data contracts for the pipeline. Every agent reads/writes these shapes
so the JSON files on disk are stable and human-readable across pipeline runs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Measured against Edge neural TTS at the +8% rate the renderer uses. Kept
# slightly conservative so scenes aren't stretched to fit their own narration.
WORDS_PER_SECOND = 2.6


class AdRecord(BaseModel):
    """One ad pulled from the Apify Meta Ads Library scraper."""

    ad_id: str
    page_name: str
    body_text: str = ""
    headline: str = ""
    cta: str = ""
    landing_page: str | None = None
    days_running: int = 0
    start_date: str | None = None
    platforms: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    media_type: Literal["image", "video", "carousel", "unknown"] = "unknown"
    raw: dict = Field(default_factory=dict)


class AdRanking(BaseModel):
    """Ranked ads for one search niche, saved verbatim to data/ads/."""

    niche: str
    keywords: list[str]
    searched_at: datetime
    window_days: int
    total_ads_found: int
    top_ads: list[AdRecord]


class AdConcept(BaseModel):
    """One marketing concept extracted from a single top-performing ad."""

    source_ad_id: str
    pain_point: str
    hook_type: str
    core_promise: str
    tone: str
    notable_phrases: list[str] = Field(default_factory=list)


class AdConceptReport(BaseModel):
    niche: str
    generated_at: datetime
    concepts: list[AdConcept]
    synthesized_patterns: list[str] = Field(
        default_factory=list,
        description="Cross-ad patterns the LLM noticed (recurring pain points, angles, proof types).",
    )


class ResearchFinding(BaseModel):
    title: str
    url: str
    published_date: str | None = None
    snippet: str


class ProprietaryDataPoint(BaseModel):
    label: str
    value: str
    source: str


class Scene(BaseModel):
    order: int
    duration_sec: float
    visual: str = Field(description="Shot description for the video agent / storyboard.")
    voiceover: str = ""
    on_screen_text: str = ""
    sfx_or_music_note: str = ""


class VideoScript(BaseModel):
    variant: Literal["pain_agitate", "proof_data", "transformation"]
    icp: str
    pain_point: str
    visual_hook: str = Field(description="What happens in the first 2-3 seconds to stop the scroll.")
    scenes: list[Scene]
    cta: str
    voiceover_full: str
    est_duration_sec: float
    source_ad_concepts: list[str] = Field(default_factory=list)
    research_refs: list[str] = Field(default_factory=list)
    proprietary_data_used: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _scene_durations_must_sum_to_a_real_ad_length(self) -> "VideoScript":
        total = sum(s.duration_sec for s in self.scenes)
        if not (28 <= total <= 62):
            raise ValueError(
                f"scene durations sum to {total}s, but a 30-60s ad needs them to add up to "
                f"that range. Increase or decrease individual scene duration_sec values "
                f"(don't just change est_duration_sec) so the sum lands in [30, 60]."
            )
        self.est_duration_sec = total
        return self

    @model_validator(mode="after")
    def _voiceover_must_be_speakable_in_the_time_allowed(self) -> "VideoScript":
        # The renderer stretches a scene to fit its narration rather than cutting
        # the line off, so overlong voiceover silently pushes the finished ad
        # past 60s. Catch it here instead.
        overruns = [
            f"scene {s.order}: {len(s.voiceover.split())} words in {s.duration_sec}s "
            f"(max ~{int(s.duration_sec * WORDS_PER_SECOND)})"
            for s in self.scenes
            if len(s.voiceover.split()) > s.duration_sec * WORDS_PER_SECOND
        ]
        if overruns:
            raise ValueError(
                "Voiceover is too long to speak in the time allotted — a narrator covers "
                f"about {WORDS_PER_SECOND} words per second. Shorten the voiceover text or "
                "lengthen those scenes: " + "; ".join(overruns)
            )
        return self


class ScriptBundle(BaseModel):
    niche: str
    generated_at: datetime
    scripts: list[VideoScript]


class VideoRenderResult(BaseModel):
    script_variant: str
    output_path: str
    duration_sec: float
    renderer: Literal["openmontage", "fallback_ffmpeg"]
    success: bool
    notes: str = ""
