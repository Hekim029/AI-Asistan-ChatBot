import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
import requests
import utils.config as config

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
        wav.write(tmp_path, sample_rate, audio)

        with open(tmp_path, "rb") as audio_file:
            response = requests.post(
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
