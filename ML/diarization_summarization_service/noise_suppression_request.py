import requests

def request_for_noise_suppression(input_audio_file_path):
    noise_suppression_URL = "http://denoiser:8052/denoise"
    print('request for noise suppression')
    with open(input_audio_file_path, "rb") as f:
        files = {"file": ("audio.wav", f, "audio/wav")}
        response = requests.post(noise_suppression_URL, files=files)
    print(response.status_code)
    if response.status_code == 200:
        with open(f"{input_audio_file_path}_clean.wav", "wb") as out:
            out.write(response.content)
        print("Очищенный файл сохранён")
        return f"{input_audio_file_path}_clean.wav"
    raise ValueError("Ошибка:", response.status_code, response.text)
    