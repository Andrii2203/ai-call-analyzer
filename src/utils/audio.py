import hashlib
import os
from dataclasses import dataclass

import miniaudio

# Azure Speech default input format: 16 kHz, 16-bit, mono PCM.
# Any other file (MP3, stereo WAV, 44.1 kHz...) is decoded and resampled to it first.
TARGET_SAMPLE_RATE = 16000


class AudioDecodeError(Exception):
    """The file exists but cannot be decoded as audio."""


@dataclass(frozen=True)
class PcmAudio:
    pcm: bytes
    sample_rate: int
    duration_sec: float


def load_pcm16_mono(audio_path: str, sample_rate: int = TARGET_SAMPLE_RATE) -> PcmAudio:
    """
    Decodes MP3, WAV, FLAC or OGG Vorbis into 16-bit mono PCM at the given sample rate.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        decoded = miniaudio.decode_file(
            audio_path,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=sample_rate,
        )
    except miniaudio.MiniaudioError as e:
        raise AudioDecodeError(f"Cannot decode audio file {audio_path}: {e}") from e

    return PcmAudio(
        pcm=decoded.samples.tobytes(),
        sample_rate=decoded.sample_rate,
        duration_sec=decoded.duration,
    )


def meeting_id_for(audio_path: str) -> str:
    """
    Derives a stable meeting_id from the file content, so re-running the pipeline
    on the same recording hits the S3/DynamoDB cache instead of paid APIs.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    digest = hashlib.sha256()
    with open(audio_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:32]
