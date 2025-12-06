import torch

_original_torch_load = torch.load

def unsafe_torch_load(*args, **kwargs):

    kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)


torch.load = unsafe_torch_load
import requests
print("Testing HF connectivity...")
r = requests.get("https://huggingface.co/pyannote/speaker-diarization-community-1", timeout=10)
print("Status:", r.status_code)
import torchaudio
import os

from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook
import pyannote.audio
import gigachat
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
import warnings
import json
from tqdm import tqdm
import openai
from openai import OpenAI
import gigaam
from time import time
from pyannote.audio.core.task import Specifications
from noise_suppression_request import request_for_noise_suppression
from whisper_request import transcribe_with_whisper_service

class AudioRecognition():

  def __init__(self, api_key_envname: str ="SBER_API_KEY", hf_api_key_envname="HF_API_KEY", openai_api_key_envname="OPENAI_API_KEY"):

    self.POSSIBLE_EXT = ('mp3', 'wav', 'mp4', 'ogg') #list of possible audio extensions (and probably video)
    self.SAMPLE_RATE = 16000 #sample rate must be 16000, bc of whisper ai
    #self.GIGACHAT_API_KEY = os.getenv(api_key_envname)
    #self.HF_API_KEY = os.getenv(hf_api_key_envname)
    #self.OPENAI_API_KEY = os.getenv(openai_api_key_envname) #getting api key from env
    self.hf_api_key_envname = hf_api_key_envname
    self.openai_api_key_envname = openai_api_key_envname
    self.whisper_model_path = "./models/faster-whisper-large-v3"
    self.SYSTEM_SUMMARIZATION_PROMPT = """\
Ты — точный и нейтральный ассистент по обработке речи. Твоя задача — создать **строго фактологическое краткое содержание** предоставленного текста.

**Правила:**
1. Используй **только информацию из текста**. Ничего не выдумывай, не интерпретируй, не добавляй.
2. Не приписывай мотивы, эмоции, цели или выводы, если они не выражены явно.
3. Сохраняй нейтральный тон. Избегай оценочных суждений.
4. Если в тексте несколько спикеров — укажи ключевые темы и позиции каждого (если они различаются).
5. Сфокусируйся на **существенных фактах, решениях, заявлениях, событиях**.
6. Не используй маркированные списки, если не указано иное. Пиши связным текстом.
7. Если текст не содержит полезной информации — напиши: "Текст не содержит существенной информации для краткого содержания."

Создай краткое содержание объёмом не более 200–300 слов.
""" #prompt for summarization
    self.SUMMARIZATION_PROMPT = "Создай краткое содержание следующего текста в соответствии с правилами выше:"
    self.SYSTEM_KEYPOINTS_PROMPT = """\
Ты — точный и нейтральный ассистент по анализу деловых и профессиональных обсуждений.  
Твоя задача — выделить **ключевые решения, события, согласованные действия и поворотные моменты**, которые произошли в ходе обсуждения.

**Правила:**
1. **Фокусируйся только на том, что было решено, согласовано, назначено или произошло.**  
   Игнорируй общие рассуждения, повторы, приветствия и вводные фразы.
2. **Чётко указывай:**
   - Кто принял решение (если указано),
   - Что именно решено/согласовано,
   - Сроки, дедлайны или временные рамки (если есть),
   - Ответственные лица (если упомянуты).
3. **Не интерпретируй**, не добавляй мотивы, эмоции или последствия, которых нет в тексте.
4. Если в тексте **нет решений, событий или согласованных действий** — напиши:  
   "В обсуждении не было принято никаких решений или согласованных действий."
5. Сохраняй **нейтральный, деловой тон**. Пиши связным текстом без маркированных списков.
6. Объём — не более 200–300 слов.
"""
    self.KEYPOINTS_PROMPT = "Создай список по решениям и рассуждениям проведенным в следующем тексте в соответствие с правилами в системном промпте"
    self.SYSTEM_QUESTIONS_PROMPT = """\
Ты — точный и нейтральный ассистент по обработке текста.  
Твоя задача — отвечать **строго на основе предоставленного текста** на заданный вопрос.

**Правила:**
1. Отвечай **только если информация содержится в тексте**.
2. **Не выдумывай**, не интерпретируй, не добавляй знания извне.
3. Если в тексте **нет информации**, необходимой для ответа на вопрос, — ответь:  
   "В предоставленном тексте недостаточно информации для ответа на этот вопрос."
4. Сохраняй **нейтральный тон**, избегай оценочных суждений и предположений.
5. Если вопрос требует уточнения, но текст всё равно не даёт однозначного ответа — используй фразу из п. 3.
6. Ответ должен быть **кратким, точным и основанным исключительно на тексте**.
"""
    self.QUESTIONS_PROMPT = "Ответь на вопросы пользователя согласно правилам из системного пропмта по следующему тексту:"
    # self.pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=self.HF_API_KEY).to(torch.device("cuda"))
    # if not(os.path.isfile("diarize_worker.py")):
    #   raise ValueError("Can't find diarize_worker.py file. Please import from github")
    # print('gigaam started')
    # print(torch.cuda.is_available())
    # print(">>> REAL pyannote.audio version:", pyannote.audio.__version__)
    # self.model = gigaam.load_model(
    #     gigaam_model,
    #     device='cuda'
    # )
    # print('gigaam installed')
    # #3.4.0
    # self.diarize_pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=os.getenv(self.hf_api_key_envname)).to(torch.device("cuda"))

  def convert_to_wav(self, input_path: str, output_wav_path: str):

    """
    Converts file to a WAV file using torchaudio.
    Args:
        input_path (str): The path to the input file.
        output_wav_path (str): The path for the output WAV file.
    """

    try:
        waveform, sample_rate = torchaudio.load(input_path)

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        if sample_rate != self.SAMPLE_RATE:
            waveform = torchaudio.functional.resample(waveform, sample_rate, self.SAMPLE_RATE)
            sample_rate = self.SAMPLE_RATE

        torchaudio.save(
            output_wav_path,
            waveform,
            sample_rate,
            format='wav',
            encoding="PCM_S",
            bits_per_sample=16
        )
        print(f"Converted '{input_path}' to '{output_wav_path}'")
    except Exception as e:
        raise RuntimeError(f"Failed to convert audio: {e}")
    return output_wav_path

  def diarize_pyannote(self, input_audio_path: str, diarize_model = "pyannote/speaker-diarization-community-1"):
    #running diarization
    print("Начало диаризации с помощью pyannote")
    # diarize_pipeline = Pipeline.from_pretrained(diarize_model, token=os.getenv(self.hf_api_key_envname)).to(torch.device("cuda"))
    diarize_pipeline = Pipeline.from_pretrained(
        "/app/pyannote-model"
    ).to(torch.device("cuda"))
    print("Модель загружена")
    waveform, sample_rate = torchaudio.load(input_audio_path)
    output = diarize_pipeline({"waveform": waveform, "sample_rate": sample_rate})
    diarization_results = []
    index = 0
    for turn, speaker in output.speaker_diarization:
        chunk_start = int(turn.start * self.SAMPLE_RATE)
        chunk_end = int(turn.end * self.SAMPLE_RATE)
        if chunk_end - chunk_start > 0.5 * self.SAMPLE_RATE: #артефакты длиной 0.5 секунд исключаем
          if index > 0:
            if diarization_results[index - 1]['Speaker'] == speaker:
              diarization_results[index - 1]['stop'] = turn.end
            else:
              diarization_results.append({"Speaker": speaker, "start": turn.start, "stop": turn.end})
              index += 1
          else:
            diarization_results.append({"Speaker": speaker, "start": turn.start, "stop": turn.end})
            index += 1

    return diarization_results

    #running transcription

  def transcribe_gigaam(self, diarization_results, input_audio_path: str, transcription_model: str = 'v3_ctc'):
    if not os.path.isfile(input_audio_path):
        raise FileNotFoundError(f"Audio file not found: {input_audio_path}")
    if os.path.getsize(input_audio_path) == 0:
        raise ValueError(f"Audio file is empty: {input_audio_path}")
    waveform, _ = torchaudio.load(input_audio_path)

    model = gigaam.load_model(
        transcription_model,
        device='cuda'
    )

    print("Начало транскрибации с помощью gigaam")
    for index, timings in tqdm(enumerate(diarization_results)):
      audio_chunk = waveform[:, int(timings['start'] * self.SAMPLE_RATE): int(timings['stop'] * self.SAMPLE_RATE)]
      resulted_transcription = ''
      print(audio_chunk.shape, self.SAMPLE_RATE)
      print(int(timings['start'] * self.SAMPLE_RATE), int(timings['stop'] * self.SAMPLE_RATE))
      for chunks in range(0, audio_chunk.shape[1], 23*self.SAMPLE_RATE):
        chunk = audio_chunk[:, chunks:chunks+23*self.SAMPLE_RATE]
        if chunk.shape[1] == 0:
            continue
        audio_output = "chunk.wav"
        torchaudio.save(uri=audio_output, src=chunk, sample_rate=self.SAMPLE_RATE)
        transcription = model.transcribe(audio_output)
        resulted_transcription += transcription
      diarization_results[index]["Text"] = resulted_transcription

    return diarization_results

  def transcribe_whisper(self, diarization_results, input_audio_path: str):
    # if not os.path.isfile(input_audio_path):
    #     raise FileNotFoundError(f"Audio file not found: {input_audio_path}")
    # if os.path.getsize(input_audio_path) == 0:
    #     raise ValueError(f"Audio file is empty: {input_audio_path}")
    # audio_waveform = decode_audio(input_audio_path)

    # model = WhisperModel(self.whisper_model_path, device='cuda')

    # print("Начало транскрибации whisper")
    # for index, timings in tqdm(enumerate(diarization_results)):
    #   audio_chunk = audio_waveform[int(timings['start'] * self.SAMPLE_RATE): int(timings['stop'] * self.SAMPLE_RATE)]
    #   segments, info = model.transcribe(audio_chunk, beam_size=5, language='ru')
    #   # segments, info = self.model.transcribe(audio_chunk, beam_size=5, language='ru')
    #   transcribed_text = ""
    #   for segment in segments:
    #     transcribed_text += segment.text
    #   diarization_results[index]["Text"] = transcribed_text
    # print(diarization_results)
    diarization_results = transcribe_with_whisper_service(diarization_results, input_audio_path)
    return diarization_results

  def run_diarization_transcription_pipeline(self, input_audio_path: str, diarization_lib: str = "pyannote", transcribe_lib: str = "gigaam", diarization_model: str = "pyannote/speaker-diarization-community-1", transcribe_model: str = "v3_ctc"):
    """
    Convert WAV file to human speech:
    Speaker: SPEAKER_00, Text: Ну и разные географические зоны.
    Speaker: SPEAKER_00, Text: Понятно, предоставляют разные возможности для этого.
    Speaker: SPEAKER_00, Text: Например, там в Африке.
    Speaker: SPEAKER_00, Text: Можно построить жилище, накрыть его пальмовыми листьями, да, через год они сгниют.
    Speaker: SPEAKER_00, Text: Новый сезон дождей, новых.
    ...
    Args:
        input_audio_path(str): The path to input file (mp4, mp3, wav only supported)
        output_save_script_file_path(str): default - None: The path to save file with transibed script. If path not specified, you will get only list(dict)
        diarization_model(str): default - pyannote: Library to use for diarization
        transcribe_model(str): default - gigaam: Library to use for transcription
    Returns:
        transcription_results(dict(str)): List with dict inside with transcribed and diarized text
                                              |
                                       [..,[{'Speaker': speaker, 'Text': text, 'start': turn.start:.1f, 'stop': turn.end:.1f},..]
    """
    #running file converting
    #---------------------------------
    if not(input_audio_path):
      raise ValueError("Input audio path cannot be empty.")

    full_path = os.path.abspath(input_audio_path)
    base_name = os.path.basename(full_path)
    file_name_root, file_ext_with_dot = os.path.splitext(base_name)
    file_ext = file_ext_with_dot[1:].lower()

    if file_ext not in self.POSSIBLE_EXT:
      raise ValueError(f"Wrong file format '{file_ext}'. Supported file formats: {', '.join(self.POSSIBLE_EXT)}")

    input_audio_path = full_path

    if file_ext != 'wav':
      wav_output_path = os.path.join(
                os.path.dirname(full_path),
                file_name_root + ".wav"
            )
      wav_input_audio_path = self.convert_to_wav(input_audio_path, wav_output_path)
    clean_wav_input_audio_path = wav_input_audio_path
    #using noise_suppression
    # clean_wav_input_audio_path = request_for_noise_suppression(wav_input_audio_path)
    #diarization model choose
    if diarization_lib == "pyannote":
      diarization_results = self.diarize_pyannote(clean_wav_input_audio_path, diarize_model=diarization_model)
    #transcription model choose
    if transcribe_lib == "gigaam":
      transcription_results = self.transcribe_gigaam(diarization_results, clean_wav_input_audio_path, transcription_model=transcribe_model)
    elif transcribe_lib == "whisper":
      print(diarization_results)
      transcription_results = self.transcribe_whisper(diarization_results, clean_wav_input_audio_path)
    return transcription_results


  def speaker_identification(self, audio_chunk, threshold):
    """
    Identify speaker by voice chunk and embedding database.
    Args:
      audio_chunk(): audio
      threshold(float): threshold for cosine similarity [0, 2]
    Returns:
      speaker_info
    """
    pass

  def summarize_with_gigachat(self, text=None, file_path=None):
    """
    Makes API call to gigachat services, summarizes given text
    Args:
        text(str): text from transcribition
        file_path(str): path to file with transcribed text
    Returns:
        summarization_results(str): summarization results
    """
    if file_path is None and text is None:
      raise ValueError("Please specify file_path or paste text")

    if file_path and text:
      warnings.warn("When text and file_path are specified in functions args, text from args(file_path) will overwrite args(text)")

    if file_path:
      with open(file_path, mode='r') as f:
        text = f.read()

    with GigaChat(credentials=self.GIGACHAT_API_KEY, verify_ssl_certs=False) as giga:
      messages = [
          Messages(role=MessagesRole.SYSTEM, content=self.GIGACHAT_SYSTEM_PROMPT),
          Messages(role=MessagesRole.USER, content=f"Создай краткое содержание следующего текста в соответствии с правилами выше:\n\n{text}")
      ]
      chat = Chat(messages=messages, temperature=0.01)
      response = giga.chat(chat)
      summarization_results = response.choices[0].message.content.strip()
      return summarization_results

    raise ValueError("Something went wrong with GigaChat API call")

  def summarize_with_openai(self, text: str = None,
                            file_path: str = None,
                            model: str = "openai/gpt-oss-20b",
                            base_url: str = "https://openrouter.ai/api/v1",
                            temperature: float = 0.01,
                            max_tokens: int = 3000,
                            task_choice: str = 'summarization'):
    """
    Makes API call to openai services, summarizes given text
    Args:
        text(str): text from transcribition
        file_path(str): path to file with transcribed text
        model (str): Model name to use for summarization
        base_url (str, optional): Custom base URL for OpenAI-compatible endpoints (e.g., for local LLMs)
    Returns:
        summarization_results(str): summarization results
    """
    if file_path is None and text is None:
      raise ValueError("Please specify file_path or paste text")

    if file_path and text:
      warnings.warn("When text and file_path are specified in functions args, text from args(file_path) will overwrite args(text)")

    if file_path:
      with open(file_path, mode='r', encoding='utf-8') as f:
        text = f.read()
    print(text)
    task_opinions_map = {'summarization': (self.SYSTEM_SUMMARIZATION_PROMPT, self.SUMMARIZATION_PROMPT), 'keypoints': (self.SYSTEM_KEYPOINTS_PROMPT, self.KEYPOINTS_PROMPT), 'questions': (self.SYSTEM_QUESTIONS_PROMPT, self.QUESTIONS_PROMPT)}
    if task_choice not in task_opinions_map.keys():
       raise ValueError(f"that task is not in: {task_opinions_map.keys()}")

    open_api_key = os.getenv(self.openai_api_key_envname)
    client = OpenAI(api_key=open_api_key, base_url=base_url)
  
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": task_opinions_map[task_choice][0]},
                {"role": "user", "content": f"{task_opinions_map[task_choice][1]}\n\n{text}"}
            ],
            temperature=temperature,
            max_tokens = max_tokens
        )
        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        raise RuntimeError(f"Error during OpenAI-compatible summarization: {e}")

  def questions_with_openai(self, text: str = None,
                            file_path: str = None,
                            model: str = "openai/gpt-oss-20b",
                            base_url: str = "https://openrouter.ai/api/v1",
                            temperature: float = 0.01,
                            max_tokens: int = 3000,
                            question: str = None):
    """
    Makes API call to openai services, summarizes given text
    Args:
        text(str): text from transcribition
        file_path(str): path to file with transcribed text
        model (str): Model name to use for summarization
        base_url (str, optional): Custom base URL for OpenAI-compatible endpoints (e.g., for local LLMs)
    Returns:
        summarization_results(str): summarization results
    """
    if file_path is None and text is None:
      raise ValueError("Please specify file_path or paste text")

    if file_path and text:
      warnings.warn("When text and file_path are specified in functions args, text from args(file_path) will overwrite args(text)")

    if file_path:
      with open(file_path, mode='r') as f:
        text = f.read()

    open_api_key = os.getenv(self.openai_api_key_envname)
    client = OpenAI(api_key=open_api_key, base_url=base_url)
  
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self.SYSTEM_QUESTIONS_PROMPT},
                {"role": "user", "content": f"{self.QUESTIONS_PROMPT}\n\n{text}\n\nА вот вопрос от пользователя: {question}"}
            ],
            temperature=temperature,
            max_tokens = max_tokens
        )
        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        raise RuntimeError(f"Error during OpenAI-compatible summarization: {e}")
# HF_API_KEY = "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" # @param {"type":"string","placeholder":"HF_API_KEY"}
# # OPENAI_API_KEY = "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" # @param {"type":"string","placeholder":"OPENAI_API_KEY"} groq key
# OPENAI_API_KEY = "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" # @param {"type":"string","placeholder":"OPENAI_API_KEY"}
# import os
# #os.environ["SBER_API_KEY"] = SBER_API_KEY
# os.environ["HF_API_KEY"] = HF_API_KEY
# os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
# loading_model = "large" # @param ["large","base","large-v3"]
# audior = AudioRecognition()
# # @title Запуск транскрибации. Укажи путь к файлу и путь к выходному файлу
# file_path = "bfda67ac521afab.mp3" # @param {"type":"string","placeholder":"test.wav"}
# output_file_path = "transcribed.txt" # @param {"type":"string","placeholder":"transcribed.txt"}
# res = audior.run_diarization_transcription_pipeline(file_path, output_file_path, "pyannote", "gigaam")
# print(res)