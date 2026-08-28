import sounddevice as sd
import tempfile
import os
import wave
import requests
import utils.config as config


def _write_pcm16_wav(path: str, audio, sample_rate: int) -> None:
    """sounddevice'ın PCM16 çıktısını ağır SciPy bağımlılığı olmadan yazar."""
    if not 8_000 <= int(sample_rate) <= 192_000:
        raise ValueError("Geçersiz örnekleme hızı.")
    dtype = getattr(audio, "dtype", None)
    if getattr(dtype, "name", "") != "int16":
        raise ValueError("Ses verisi 16 bit PCM olmalıdır.")
    shape = getattr(audio, "shape", ())
    channels = int(shape[1]) if len(shape) > 1 else 1
    if not 1 <= channels <= 8:
        raise ValueError("Geçersiz ses kanalı sayısı.")
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(audio.tobytes())

def listen_and_transcribe(duration: int = 3, sample_rate: int = 16000) -> str | None:
    tmp_path = None
    try:
        if not config.GROQ_API_KEY:
            return None

        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                      channels=1, dtype='int16')
        sd.wait()

        fd, tmp_path = tempfile.mkstemp(prefix="heko_audio_", suffix=".wav")
        os.close(fd)
        _write_pcm16_wav(tmp_path, audio, sample_rate)

        with open(tmp_path, "rb") as audio_file:
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={
                        "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    },
                    files={
                        "file": ("heko_audio.wav", audio_file, "audio/wav"),
                    },
                    data={
                        "model": "whisper-large-v3-turbo",
                        "language": "tr",
                        "response_format": "json",
                        "temperature": "0",
                    },
                    timeout=30,
                    allow_redirects=False,
                )
        response.raise_for_status()
        return (response.json().get("text") or "").strip() or None

    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
