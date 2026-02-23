import torch

_original_torch_load = torch.load

def unsafe_torch_load(*args, **kwargs):

    kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)


torch.load = unsafe_torch_load
import requests
import torchaudio
import os
import sys

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
from pyannote.audio.core.task import Specifications
from noise_suppression_request import request_for_noise_suppression
from whisper_request import transcribe_with_whisper_service
import logging
from prompts.prompt_loader import PromptLoader

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
)

logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

class AudioRecognition():

  def __init__(self, hf_api_key_envname="HF_API_KEY", openai_api_key_envname="OPENAI_API_KEY", prompts_path="prompts/llm_prompts.yaml"):

    self.POSSIBLE_EXT = ('mp3', 'wav', 'mp4', 'ogg') #list of possible audio extensions (and probably video)
    self.SAMPLE_RATE = 16000 #sample rate must be 16000, bc of whisper ai
    self.hf_api_key_envname = hf_api_key_envname
    self.openai_api_key_envname = openai_api_key_envname
    self.prompts_path = prompts_path
    self.prompts = PromptLoader(self.prompts_path)
    self.SYSTEM_SUMMARIZATION_PROMPT = self.prompts.get("summarization.system")
    self.SUMMARIZATION_PROMPT = self.prompts.get("summarization.user")
    self.SYSTEM_KEYPOINTS_PROMPT = self.prompts.get("keypoints.system")
    self.KEYPOINTS_PROMPT = self.prompts.get("keypoints.user")
    self.SYSTEM_QUESTIONS_PROMPT = self.prompts.get("questions.system")
    self.QUESTIONS_PROMPT = self.prompts.get("questions.user")
    with open("ontology.txt") as f:
      self.ontology_file_text = f.read()
    self.ALLOWED_MEETING_TYPES = {
      "Оперативное совещание",
      "Стратегическое совещание",
      "Финансовое совещание",
      "HR-совещание",
      "Обзор проекта",
      "Экстренное совещание"
    }

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
        logging.info(f"Converted '{input_path}' to '{output_wav_path}'")
    except Exception as e:
        logging.error(f"Failed to convert audio: {e}")
        raise RuntimeError(f"Failed to convert audio: {e}")
    return output_wav_path

  def diarize_pyannote(self, input_audio_path: str, diarize_model = "pyannote/speaker-diarization-community-1"):
    #running diarization
    logging.info("Начало диаризации с помощью pyannote")
    MODEL_PATH = os.getenv("PYANNOTE_MODEL_PATH", "/app/models/pyannote")
    diarize_pipeline = Pipeline.from_pretrained(MODEL_PATH).to(torch.device("cuda"))
    logging.info("Модель загружена")
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

    logging.info("Начало транскрибации с помощью gigaam")
    for index, timings in tqdm(enumerate(diarization_results)):
      audio_chunk = waveform[:, int(timings['start'] * self.SAMPLE_RATE): int(timings['stop'] * self.SAMPLE_RATE)]
      resulted_transcription = ''
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
    logging.info('whisper transcription')
    diarization_results = transcribe_with_whisper_service(diarization_results, input_audio_path)
    return diarization_results

  def run_diarization_transcription_pipeline(self, input_audio_path: str, diarization_lib: str = "pyannote", transcribe_lib: str = "gigaam", diarization_model: str = "pyannote/speaker-diarization-community-1", transcribe_model: str = "v3_ctc", noise_sup_bool: bool = True):
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
      logging.error(f"Wrong file format '{file_ext}'")
      raise ValueError(f"Wrong file format '{file_ext}'. Supported file formats: {', '.join(self.POSSIBLE_EXT)}")

    input_audio_path = full_path

    if file_ext != 'wav':
      wav_output_path = os.path.join(
                os.path.dirname(full_path),
                file_name_root + ".wav"
            )
      wav_input_audio_path = self.convert_to_wav(input_audio_path, wav_output_path)
    else:
      wav_input_audio_path = input_audio_path
    #using noise_suppression
    # if noise_sup_bool:
    #   print("go to noise suppressor")
    #   clean_wav_input_audio_path = request_for_noise_suppression(wav_input_audio_path)
    # else:
    clean_wav_input_audio_path = wav_input_audio_path
    clean_wav_input_audio_path = self.convert_to_wav(clean_wav_input_audio_path, clean_wav_input_audio_path)
    #diarization model choose
    if diarization_lib == "pyannote":
      diarization_results = self.diarize_pyannote(clean_wav_input_audio_path, diarize_model=diarization_model)
    #transcription model choose
    if transcribe_lib == "gigaam":
      transcription_results = self.transcribe_gigaam(diarization_results, clean_wav_input_audio_path, transcription_model=transcribe_model)
    elif transcribe_lib == "whisper":
      # transcription_results = self.transcribe_whisper(diarization_results, clean_wav_input_audio_path)
      transcription_results = self.transcribe_whisper(diarization_results, clean_wav_input_audio_path)
    return transcription_results

  def summarize_with_openai(self, text: str = None,
                            file_path: str = None,
                            model: str = "arcee-ai/trinity-mini:free",
                            base_url: str = "https://openrouter.ai/api/v1",
                            temperature: float = 0.01,
                            max_tokens: int = 3000):
    """
    Makes API call to openai services, summarizes given text
    Args:
        text(str): text from transcribition
        file_path(str): path to file with transcribed text
        model (str): Model name to use for summarization
        base_url (str, optional): Custom base URL for OpenAI-compatible endpoints (e.g., for local LLMs)
    Returns:
        {
        "title": "...",
        "summary": "...",
        "key_points": ["...", "...", ...]
        }
    """
    if file_path is None and text is None:
      raise ValueError("Please specify file_path or paste text")

    if file_path and text:
      warnings.warn("When text and file_path are specified in functions args, text from args(file_path) will overwrite args(text)")

    if file_path:
      with open(file_path, mode='r', encoding='utf-8') as f:
        text = f.read()
    system_prompt = (
        "Ты — точный и нейтральный ассистент по анализу деловых совещаний."
        "Твоя задача — проанализировать предоставленный текст и вернуть ТОЛЬКО валидный JSON о названии совещания, о кратком содержании текста и о ключевых моментах совещания в следующем формате:\n"
        "{\n"
        '  "title": "Краткое название совещания (5–7 слов, описательное, без кавычек)",\n'
        '  "summary": "Фактологическое краткое содержание (200–300 слов). Используй только информацию из текста. Не выдумывай. Нейтральный тон. Связный текст.",\n'
        '  "key_points": [\n'
        '    "Ключевой момент совещания 1",\n'
        '    "Ключевой момент совещания 2",\n'
        '    ...\n'
        "  ]\n"
        "}\n\n"
        "Правила:\n"
        "- Отвечать только на РУССКОМ ЯЗЫКЕ.\n"
        "- Все поля обязательны.\n"
        "- В key_points включай любые решения, назначения, согласованные действия или события, даже если они описаны в обобщённой форме (например: «было решено назначить», «установлено проводить встречи», «договорились внедрить», «планируется развивать»).\n"
        "- Обращай внимание на глаголы: «решено», «назначено», «установлено», «согласовано», «планируется», «необходимо», «будет проводиться», «поручено», «принято» — такие фразы считаются решениями.\n"
        "- Не требуй прямой речи или имён спикеров. Достаточно упоминания действия в контексте соглашения или плана.\n"
        "- Игнорируй только общие рассуждения без намёка на действие (например: «курс важный», «нужно подумать»).\n"
        "- Если и только если в тексте действительно отсутствуют какие-либо решения, назначения или согласованные действия — тогда key_points должен содержать одну строку: \"В обсуждении не было принято никаких решений или согласованных действий.\"\n"
        "- Если текст пуст или бессодержателен — summary: \"Текст не содержит существенной информации для краткого содержания.\"\n"
        "- Никакого дополнительного текста, пояснений, форматирования. Только JSON."
    )

    open_api_key = os.getenv(self.openai_api_key_envname)
    client = OpenAI(api_key=open_api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Анализируй следующий текст совещания:\n\n{text}"}
            ],
            temperature=temperature,
            max_tokens = max_tokens,
            response_format={
              "type": "json_schema",
              "json_schema": {
                  "name": "meeting_analysis",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "title": {"type": "string"},
                          "summary": {"type": "string"},
                          "key_points": {"type": "array", "items": {"type": "string"}},
                      },
                      "required": ["title", "summary", "key_points"]
                  }
              },
              "plugins": [
              {"id": "response-healing"}
              ]
            },
        )
        raw = response.choices[0].message.content.strip()
        try:
            result = json.loads(raw)
            for key in ["title", "summary", "key_points"]:
                if key not in result:
                    raise ValueError(f"Отсутствует поле: {key}")
            if not isinstance(result["key_points"], list):
                raise ValueError("key_points должен быть списком") # ! Место которое надо исправить, похоже придется делать retry
            return result
        except json.JSONDecodeError as e:
            logging.error(f"Модель вернула невалидный JSON:\n{raw}: {e}")
            raise RuntimeError(f"Модель вернула невалидный JSON:\n{raw}") from e

    except Exception as e:
        logging.error(f"Error during OpenAI-compatible summarization: {e}")
        raise RuntimeError(f"Error during OpenAI-compatible summarization: {e}") from e

  def classify_meeting_type_with_openai(self, text: str, 
                                        model: str = "arcee-ai/trinity-mini:free", 
                                        base_url: str = "https://openrouter.ai/api/v1",
                                        temperature: float = 0.001,
                                        max_tokens: int = 3000) -> str:
    system_prompt = (
        "Ты — эксперт по анализу деловых совещаний. Используй онтологию ниже для определения типа совещания.\n\n"
        f"{self.ontology_file_text}\n\n"
        "Верни ТОЛЬКО название типа совещания из списка:\n"
        '"Оперативное совещание", "Стратегическое совещание", "Финансовое совещание", '
        '"HR-совещание", "Обзор проекта", "Экстренное совещание".\n'
        "Никаких пояснений, только одно название."
    )
    client = OpenAI(api_key=os.getenv(self.openai_api_key_envname), base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Текст совещания:\n{text}"}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    raw = response.choices[0].message.content.strip()

    allowed = {
        "Оперативное совещание", "Стратегическое совещание", "Финансовое совещание",
        "HR-совещание", "Обзор проекта", "Экстренное совещание"
    }
    if raw in allowed:
        return raw
    else:
        return self._fallback_classification(text)
    
  def _fallback_classification(self, text: str) -> str:
    text_lower = text.lower()
    keywords_map = {
        "Оперативное совещание": ["статус", "задача", "срок", "блокер", "назначить"],
        "Стратегическое совещание": ["стратегия", "рынок", "цель", "план", "перспектива"],
        "Финансовое совещание": ["бюджет", "расход", "доход", "квартал", "финансы", "q1", "q2", "q3", "q4"],
        "HR-совещание": ["сотрудник", "зарплата", "собеседование", "мотивация", "увольнение", "hr"],
        "Обзор проекта": ["проект", "этап", "риск", "клиент", "сдача", "одобрить"],
        "Экстренное совещание": ["авария", "ошибка", "срочно", "исправить", "падение", "критично"]
    }
    scores = {}
    for meeting_type, keywords in keywords_map.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[meeting_type] = score
    if scores:
        return max(scores, key=scores.get)
    return "Не определено"
  
  def questions_with_openai(self, text: str = None,
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
    if text is None:
      raise ValueError("Please specify text")

    if question is None:
      raise ValueError("Please specify question")
    
    open_api_key = os.getenv(self.openai_api_key_envname)
    client = OpenAI(api_key=open_api_key, base_url=base_url)
    logging.info(f"{self.QUESTIONS_PROMPT}\n\n{text}\n\nА вот вопрос от пользователя: {question}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self.SYSTEM_QUESTIONS_PROMPT},
                {"role": "user", "content": f"{self.QUESTIONS_PROMPT}\n\n{text}\n\nА вот вопрос от пользователя:\n\n {question}"}
            ],
            temperature=temperature,
            max_tokens = max_tokens
        )
        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        logging.error(f"Error during OpenAI-compatible summarization: {e}")
        raise RuntimeError(f"Error during OpenAI-compatible summarization: {e}")