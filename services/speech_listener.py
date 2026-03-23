import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
import requests

def listen_and_transcribe(duration: int = 3, sample_rate: int = 16000) -> str | None:
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                      channels=1, dtype='int16')
        sd.wait()

        tmp_path = os.path.join(tempfile.gettempdir(), "heko_audio.wav")
        wav.write(tmp_path, sample_rate, audio)

        with open(tmp_path, 'rb') as f:
            audio_data = f.read()

        response = requests.post(
            "http://www.google.com/speech-api/v2/recognize"
            "?output=json&lang=tr-TR&key=AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw",
            headers={"Content-Type": "audio/l16; rate=16000"},
            data=audio_data
        )

        for line in response.text.strip().split('\n'):
            if '"transcript"' in line:
                import json
                data = json.loads(line)
                return data['result'][0]['alternative'][0]['transcript']
        return None

    except Exception as e:
        return None