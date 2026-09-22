import wave
from pathlib import Path

import pytest

from src.utils.audio import (
    TARGET_SAMPLE_RATE,
    AudioDecodeError,
    load_pcm16_mono,
    meeting_id_for,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_mp3_is_decoded_to_16k_mono_pcm():
    # tone.mp3: 1 s, 440 Hz, 44.1 kHz stereo -> must come out 16 kHz mono 16-bit
    audio = load_pcm16_mono(str(FIXTURES / "tone.mp3"))
    assert audio.sample_rate == TARGET_SAMPLE_RATE
    assert audio.duration_sec == pytest.approx(1.0, abs=0.1)
    assert len(audio.pcm) == pytest.approx(TARGET_SAMPLE_RATE * 2 * audio.duration_sec, rel=0.01)
    assert any(audio.pcm)  # not silence


def test_stereo_44k_wav_is_downmixed_and_resampled(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x10\x00\x10\x00" * 44100)  # 1 s
    audio = load_pcm16_mono(str(path))
    assert audio.sample_rate == TARGET_SAMPLE_RATE
    assert len(audio.pcm) == pytest.approx(TARGET_SAMPLE_RATE * 2, rel=0.01)


def test_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_pcm16_mono("no_such_file.mp3")


def test_not_audio_raises_decode_error(tmp_path):
    path = tmp_path / "notes.mp3"
    path.write_bytes(b"this is not audio" * 100)
    with pytest.raises(AudioDecodeError):
        load_pcm16_mono(str(path))


def test_meeting_id_depends_only_on_content(tmp_path):
    a = tmp_path / "a.mp3"
    b = tmp_path / "copy_of_a.mp3"
    c = tmp_path / "c.mp3"
    a.write_bytes(b"same bytes")
    b.write_bytes(b"same bytes")
    c.write_bytes(b"other bytes")
    assert meeting_id_for(str(a)) == meeting_id_for(str(b))
    assert meeting_id_for(str(a)) != meeting_id_for(str(c))
    assert len(meeting_id_for(str(a))) == 32
