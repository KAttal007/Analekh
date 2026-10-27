"""Earnings-call audio to timestamped text (design doc 9.3, transcripts).

SEBI: listed companies put call recording online within 24 hours, days before written transcript
(due in 5 working days). Transcribing the recording gives same-day notes; official transcript
replaces this text when it arrives.

Whisper (large-v3) via faster-whisper/CTranslate2, GPU when present. Voice activity filter skips
hold music and silence; initial prompt carries company name and finance vocabulary (Whisper
mishears otherwise). No speaker separation: Indian calls announce each questioner ("The next
question is from ..."), which docs/transcripts.py already uses.

Numbers are speech-to-text's weakest spot ("fifteen" vs "fifty"): anything generated from this
text is grounded against it and cross-checked with filed XBRL before shown.

Install: ``uv sync --group audio``.
"""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_MODEL = "large-v3"
VOCABULARY = (
    "Earnings call for the quarter. Revenue, EBITDA, EBIT, PAT, margins in basis points, "
    "crore, lakh, year on year, quarter on quarter, guidance, order book, deal wins, attrition, "
    "net interest margin, NIM, GNPA, NNPA, CASA, credit cost, premium, combined ratio."
)


@dataclass
class Segment:
    start: float  # seconds from the start of the recording
    end: float
    text: str
    avg_logprob: float  # Whisper's confidence; well below -1 means likely misheard
    no_speech_prob: float


@dataclass
class AudioTranscript:
    source: str
    model: str
    device: str
    language: str
    duration: float  # seconds of audio
    seconds_taken: float
    segments: list[Segment] = field(default_factory=list)

    def text(self) -> str:
        """Plain text with a [hh:mm:ss] mark per segment, so quotes can point at the recording."""
        return "\n".join(f"[{_clock(s.start)}] {s.text}" for s in self.segments)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)


def _clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _add_cuda_dll_dirs() -> None:
    """On Windows, CTranslate2 loads cuBLAS and cuDNN from the PATH; the NVIDIA pip wheels put
    their DLLs under site-packages/nvidia/*/bin, which is not on it."""
    if sys.platform != "win32":
        return
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if nvidia.is_dir():
            for bin_dir in nvidia.glob("*/bin"):
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def transcribe(
    path: Path,
    *,
    company: str | None = None,
    model: str = DEFAULT_MODEL,
    device: str = "auto",
    language: str = "en",
) -> AudioTranscript:
    """Transcribe one recording (mp3, m4a, mp4, wav, webm: anything FFmpeg reads)."""
    _add_cuda_dll_dirs()
    from faster_whisper import WhisperModel  # optional dependency group "audio"

    started = time.monotonic()
    try:
        whisper = WhisperModel(model, device=device, compute_type="default")
        used = "cuda" if device in ("auto", "cuda") and _has_cuda() else "cpu"
    except (RuntimeError, ValueError):  # no usable GPU: fall back rather than fail
        whisper = WhisperModel(model, device="cpu", compute_type="int8")
        used = "cpu"
    prompt = f"{company} {VOCABULARY}" if company else VOCABULARY
    segments, info = whisper.transcribe(
        str(path),
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,  # stops one misheard phrase repeating for minutes
    )
    out = AudioTranscript(
        source=path.name,
        model=model,
        device=used,
        language=info.language,
        duration=round(info.duration, 1),
        seconds_taken=0.0,
        segments=[
            Segment(
                round(s.start, 2),
                round(s.end, 2),
                s.text.strip(),
                round(s.avg_logprob, 3),
                round(s.no_speech_prob, 3),
            )
            for s in segments  # a generator: decoding happens here
        ],
    )
    out.seconds_taken = round(time.monotonic() - started, 1)
    return out


def _has_cuda() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001 - any failure here just means "no GPU"
        return False
