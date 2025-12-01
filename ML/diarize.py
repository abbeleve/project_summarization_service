import gigaam
import torchaudio
from time import time
import os
import json
import torch

results_path = 'whisper_analog_bench.json'
with open(results_path, encoding='utf-8') as f:
    results = json.load(f)

print(torch.cuda.is_available())

original_name = "bfda67ac521afab.mp3"
waveform, sample_rate = torchaudio.load(original_name)
waveform = waveform[0]
print(waveform.shape, sample_rate)
resulted_transcription = ''
index = 0
original_name_cutted = original_name.split('.')[0]
model_list = ['v3_ctc', 'v3_rnnt', 'v3_e2e_ctc', 'v3_e2e_rnnt']
for model_name in model_list:
    print(model_name)
    print('*'*50)
    results[model_name] = {}
    model = gigaam.load_model(
        model_name,
        device='cuda'
    )
    start_time = time()
    resulted_transcription = ''
    for chunks in range(0, len(waveform), 23*sample_rate):
        chunk = waveform[chunks:chunks+23*sample_rate]
        chunk = chunk.unsqueeze(0)
        audio_output = 'chunked_' + original_name_cutted + '.mp3'
        torchaudio.save(uri=audio_output, src=chunk, sample_rate=sample_rate)
        transcription = model.transcribe(audio_output)
        resulted_transcription += transcription