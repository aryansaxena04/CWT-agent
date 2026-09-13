import json

import pytest
from pydantic import ValidationError

from src.schemas import Scene, VideoScript


def _script(**overrides):
    defaults = dict(
        variant="pain_agitate",
        icp="retail swing trader",
        pain_point="missing entries while at work",
        visual_hook="Phone buzzes mid-meeting; a chart spikes on screen.",
        scenes=[Scene(order=i, duration_sec=7, visual=f"shot {i}", voiceover="Short line.") for i in range(1, 6)],
        cta="Get real-time alerts at crowdwisdomtrading.com",
        voiceover_full="Short line.",
        est_duration_sec=35,
    )
    return VideoScript(**{**defaults, **overrides})


def test_rejects_scene_durations_that_dont_add_up_to_an_ad():
    with pytest.raises(ValidationError, match="30-60s ad"):
        _script(scenes=[Scene(order=1, duration_sec=3, visual="a", voiceover="Hi.")])


def test_rejects_voiceover_too_long_to_speak_in_the_scene():
    wordy = "word " * 60  # ~60 words is far more than 7s of narration
    with pytest.raises(ValidationError, match="too long to speak"):
        _script(scenes=[Scene(order=i, duration_sec=7, visual="a", voiceover=wordy) for i in range(1, 6)])


def test_video_script_round_trips_through_json():
    script = VideoScript(
        variant="pain_agitate",
        icp="retail swing trader",
        pain_point="missing entries while at work",
        visual_hook="Phone buzzes mid-meeting; a chart spikes on screen.",
        scenes=[
            Scene(order=1, duration_sec=6, visual="close-up on phone notification", voiceover="You saw it too late."),
            Scene(order=2, duration_sec=7, visual="trader staring at missed gains", voiceover="Again."),
            Scene(order=3, duration_sec=8, visual="wide shot, trader alone at desk", voiceover="Every time."),
            Scene(order=4, duration_sec=8, visual="phone lights up with a CWT alert", voiceover="Not anymore."),
            Scene(order=5, duration_sec=6, visual="trader smiles, closes laptop", voiceover="Get the edge."),
        ],
        cta="Get real-time alerts at crowdwisdomtrading.com",
        voiceover_full="You saw it too late. Again. Every time. Not anymore. Get the edge.",
        est_duration_sec=35,
    )

    payload = json.loads(script.model_dump_json())
    restored = VideoScript.model_validate(payload)

    assert restored.variant == "pain_agitate"
    assert len(restored.scenes) == 5
    assert restored.scenes[0].order == 1
    assert restored.est_duration_sec == 35  # validator recomputes from scene sum
