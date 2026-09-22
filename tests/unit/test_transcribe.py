import wave
from types import SimpleNamespace
from unittest.mock import patch

import azure.cognitiveservices.speech as speechsdk
import pytest

from src.lambdas.transcribe import handler as transcribe_module
from src.lambdas.transcribe.handler import (
    TranscriptionError,
    TransientTranscriptionError,
    handler,
    transcribe_audio,
)


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, cb):
        self.callbacks.append(cb)

    def fire(self, evt):
        for cb in self.callbacks:
            cb(evt)


class FakeRecognizer:
    """Stands in for speechsdk.SpeechRecognizer and fires the events a real session would."""

    instances = []

    def __init__(self, texts=(), cancel_code=None, finish=True, **_):
        self.texts = texts
        self.cancel_code = cancel_code
        self.finish = finish
        self.recognized = FakeSignal()
        self.session_stopped = FakeSignal()
        self.canceled = FakeSignal()
        FakeRecognizer.instances.append(self)

    def start_continuous_recognition(self):
        for text in self.texts:
            result = SimpleNamespace(reason=speechsdk.ResultReason.RecognizedSpeech, text=text)
            self.recognized.fire(SimpleNamespace(result=result))
        if self.cancel_code is not None:
            details = SimpleNamespace(
                reason=speechsdk.CancellationReason.Error,
                code=self.cancel_code,
                error_details="simulated failure",
            )
            self.canceled.fire(SimpleNamespace(cancellation_details=details))
        elif self.finish:
            self.session_stopped.fire(SimpleNamespace())

    def stop_continuous_recognition(self):
        pass


def fake_recognizer_factory(**behaviour):
    def factory(**kwargs):
        return FakeRecognizer(**behaviour, **kwargs)
    return factory


@pytest.fixture
def wav_file(tmp_path):
    path = tmp_path / "call.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)  # 1 s of silence
    return str(path)


@pytest.fixture(autouse=True)
def azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    FakeRecognizer.instances.clear()


@pytest.fixture
def sleeps():
    """Records retry back-off sleeps instead of waiting."""
    with patch("src.utils.retry.time.sleep") as mock_sleep:
        yield mock_sleep


def test_transcribe_audio_success(wav_file, sleeps):
    factory = fake_recognizer_factory(texts=["Hello world.", "Second part."])
    with patch.object(transcribe_module.speechsdk, "SpeechRecognizer", side_effect=factory):
        assert transcribe_audio(wav_file) == "Hello world. Second part."
    assert len(FakeRecognizer.instances) == 1
    sleeps.assert_not_called()


def test_transcribe_audio_file_not_found_fails_fast(sleeps):
    with pytest.raises(FileNotFoundError):
        transcribe_audio("non_existent.mp3")
    sleeps.assert_not_called()


def test_transcribe_audio_no_creds_fails_fast(wav_file, monkeypatch, sleeps):
    monkeypatch.delenv("AZURE_SPEECH_KEY")
    with pytest.raises(TranscriptionError, match="Azure Speech credentials not configured"):
        transcribe_audio(wav_file)
    sleeps.assert_not_called()


def test_authentication_failure_is_reported_not_retried(wav_file, sleeps):
    factory = fake_recognizer_factory(
        cancel_code=speechsdk.CancellationErrorCode.AuthenticationFailure
    )
    with patch.object(transcribe_module.speechsdk, "SpeechRecognizer", side_effect=factory):
        with pytest.raises(TranscriptionError, match="AuthenticationFailure") as exc_info:
            transcribe_audio(wav_file)
    assert not isinstance(exc_info.value, TransientTranscriptionError)
    assert len(FakeRecognizer.instances) == 1
    sleeps.assert_not_called()


def test_connection_failure_is_retried(wav_file, sleeps):
    factory = fake_recognizer_factory(
        cancel_code=speechsdk.CancellationErrorCode.ConnectionFailure
    )
    with patch.object(transcribe_module.speechsdk, "SpeechRecognizer", side_effect=factory):
        with pytest.raises(TransientTranscriptionError, match="ConnectionFailure"):
            transcribe_audio(wav_file)
    assert len(FakeRecognizer.instances) == 4  # 1 attempt + 3 retries
    assert sleeps.call_count == 3


def test_session_that_never_ends_times_out(wav_file, sleeps):
    factory = fake_recognizer_factory(finish=False)
    with patch.object(transcribe_module, "_wait_timeout_sec", return_value=0.05):
        with patch.object(transcribe_module.speechsdk, "SpeechRecognizer", side_effect=factory):
            with pytest.raises(TransientTranscriptionError, match="did not finish"):
                transcribe_audio(wav_file)


def test_silence_gives_clear_error(wav_file, sleeps):
    factory = fake_recognizer_factory(texts=[])
    with patch.object(transcribe_module.speechsdk, "SpeechRecognizer", side_effect=factory):
        with pytest.raises(TranscriptionError, match="empty result"):
            transcribe_audio(wav_file)
    sleeps.assert_not_called()


def test_handler_meeting_id_is_stable_for_same_file(wav_file):
    with patch.object(transcribe_module, "transcribe_audio", return_value="Hello there"):
        first = handler(wav_file)
        second = handler(wav_file)
    assert first["meeting_id"] == second["meeting_id"]
    assert first["word_count"] == 2
    assert isinstance(first["created_at"], str)  # JSON-ready for S3
