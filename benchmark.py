# @title Чисто для суммаризации, потому что Dependency hell
import os
import warnings
import json
from tqdm import tqdm
import openai
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

openai_api_key_envname = "OPENAI_API_KEY"
SYSTEM_PROMPT = """\
  Ты — точный и нейтральный ассистент по обработке речи. Твоя задача — создать **строго фактологическое краткое содержание** предоставленного текста.

  **Правила:**
  1. Используй **только информацию из текста**. Ничего не выдумывай, не интерпретируй, не добавляй.
  2. Не приписывай мотивы, эмоции, цели или выводы, если они не выражены явно.
  3. Сохраняй нейтральный тон. Избегай оценочных суждений.
  4. Если в тексте несколько спикеров — укажи ключевые темы и позиции каждого (если они различаются).
  5. Сфокусируйся на **существенных фактах, решениях, заявлениях, событиях**.
  6. Не используй маркированные списки, если не указано иное. Пиши связным текстом.
  7. Если текст не содержит полезной информации — напиши: "Текст не содержит существенной информации для краткого содержания."

  Создай краткое содержание объёмом не более 200–300 слов"""

def summarize_with_openai(prompt: str = None,
                            file_path: str = None,
                            model: str = "qwen/qwen3-30b-a3b",
                            base_url: str = "https://openrouter.ai/api/v1",
                            temperature: float = 0.01,
                            max_tokens: int = 500,
                            system_prompt = SYSTEM_PROMPT,
                            openai_api_key: str = "",
                          ):
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
    if file_path is None and prompt is None:
      raise ValueError("Please specify file_path or paste text")

    if file_path and prompt:
      warnings.warn("When text and file_path are specified in functions args, text from args(file_path) will overwrite args(text)")

    if file_path:
      with open(file_path, mode='r') as f:
        prompt = f.read()
    # open_api_key = os.getenv(openai_api_key_envname)
    client = OpenAI(api_key=openai_api_key, base_url=base_url)

    print(f"Промпт размером {len(prompt)}")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens = max_tokens
        )
        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        raise RuntimeError(f"Error during OpenAI-compatible summarization: {e}")

import json

class AnsweringQuestions():
  '''
  '''
  @staticmethod
  def answer(script_file_path, llm_name, base_url, token):
    with open(script_file_path, mode='r', encoding='utf-8') as f:
      script = json.load(f)
      print(script.keys())
    for file_names in script.keys(): #TS004...
      print(file_names)
      meeting_json = script[file_names]

      meeting_transcript = ''
      for speech in meeting_json['meeting_transcripts']:
        meeting_transcript += f"{speech['speaker']}: {speech['content']}\n"

      if f'answer_{llm_name}' in meeting_json['general_query_list'][0].keys():
        pass
      else:
        # general_summarization_target = meeting_json['general_query_list']
        prompt = f"Выполни суммаризацию в соответствии с правилами в системном запросе: {meeting_transcript}"
        general_summarization_prediction = summarize_with_openai(prompt=meeting_transcript, max_tokens=2000, model=llm_name, openai_api_key=token, base_url=base_url)
        meeting_json['general_query_list'][0][f'answer_{llm_name}'] = general_summarization_prediction


      SPECIFIC_QUERY_SYSTEM_PROMPT = """\
Ты — точный и нейтральный ассистент по обработке речи. Твоя задача — создать **строго ответить на вопросы** по предоставленному тексту.

**Правила:**
1. Используй **только информацию из текста**. Ничего не выдумывай, не интерпретируй, не добавляй.
2. Не приписывай мотивы, эмоции, цели или выводы, если они не выражены явно.
3. Сохраняй нейтральный тон. Избегай оценочных суждений.
4. Сфокусируйся на **существенных фактах, решениях, заявлениях, событиях**.
5. Не используй маркированные списки, если не указано иное. Пиши связным текстом.
6. Если текст не содержит полезной информации — напиши: "Текст не содержит существенной информации для краткого содержания."

Создай краткий ответ длиной от 200-300 слов"""

      prompt = f'''
Ответь на вопросы каждый на новой строчке следующим форматом длиной хотя бы в 100 слов:
1. [ответ на первый вопрос]
2. [ответ на второй вопрос]

Отвечаешь на вопрос согласно правилам из system_prompt на следующие вопросы:
Вопросы: '''

      defined_queries = 0
      query_index = 0
      for index, specific_queries in enumerate(meeting_json['specific_query_list']):
        if f'answer_{llm_name}' in meeting_json['specific_query_list'][index].keys():
          defined_queries += 1
          pass
        else:
          prompt += f"\n{query_index + 1}. {specific_queries['query']}"
          query_index += 1

      prompt += f"\n Вот основной текст откуда берешь ответы на вопросы, тот самый текст для анализа: {meeting_transcript}"

      if defined_queries < len(meeting_json['specific_query_list']):
        print(f'need to answer: {len(meeting_json['specific_query_list']) - defined_queries}/{len(meeting_json['specific_query_list'])}')
        specific_query_answer = summarize_with_openai(prompt=prompt, model=llm_name, system_prompt=SPECIFIC_QUERY_SYSTEM_PROMPT, max_tokens=3000, base_url=base_url, openai_api_key=token)
        ans = specific_query_answer.split('\n')
        ans = [s[3:] for s in ans if s.strip()] #Dropping first 3 letters like 0. 1.

        if len(ans) != len(meeting_json['specific_query_list']) - defined_queries: #defined_queries amount of defined answers so NEED to answer is ALL answers - DEFINED answers
          print(ans)
          raise ValueError("length of llm answer is not equal to amount of queries")

        ans_index = 0
        for index, specific_query in enumerate(meeting_json['specific_query_list']):
          if f'answer_{llm_name}' in specific_query.keys(): #Check if answer is already DEFINED, so you skip it and define the first without answer
            pass
            '''
            "query":
            "answer": <- no answer so skip
        {
            "query":
            "answer":
            "answer_{llm_name}": <- we are checking for that cases
            '''
          else:
            specific_query[f'answer_{llm_name}'] = ans[ans_index] #Hard coded llm naming | Also ans_index is helping index only for ans because len(ans) != len(meeting_json['specific_query_list']), cuz len(ans) defined by amount of DEFINED answers but len(meeting_json['specific_query_list']) is defined only by file
            ans_index += 1

      if defined_queries == len(meeting_json['specific_query_list']):
        print(f"Specific queries already been answered {defined_queries}/{len(meeting_json['specific_query_list'])}")

    with open(script_file_path, mode='w', encoding='utf-8') as json_f:
        json.dump(script, json_f, ensure_ascii=False, indent=2) #Making one big commit to main file
    return True

from evaluate import load
import warnings
import torch
from transformers import BertForSequenceClassification, BertTokenizer
import gc

class BenchMarking():
  '''
  Need to create json like that:
  {
    TS004: {
      qwen30b: {
        bertscore: {
          general_query: 0.99
          specific_query_avg: 0.99
        },
        factcc: {
          general_query: 0.99
          specific_query_avg: 0.99
        }
      },
      qwen7b: {
        bertscore: {
          general_query: 0.98
          specific_query_avg: 0.98
        },
        factcc: {
          ...
        }
      }
    }
  }
  '''
  @staticmethod
  def benchmark(benchmarks_results_json_path: str, scripts_json_path: str, model_list: dict):


    if benchmarks_results_json_path in os.listdir():
      pass
    else:
      warnings.warn("Couldn't find benchmark file, creating new one")
      if benchmarks_results_json_path[-5:] == '.json':
        pass
      else:
        benchmarks_results_json_path += '.json'
      with open(benchmarks_results_json_path, mode='w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False)

    with open(benchmarks_results_json_path, mode='r', encoding='utf-8') as f:
      benchmark_results = json.load(f)
    with open(scripts_json_path, mode='r', encoding='utf-8') as f:
      script = json.load(f)
    benchmarks_results = {}
    for file_names in script.keys(): #TS004...
      print(file_names)
      benchmarks_results[file_names] = {}
      meeting_json = script[file_names]
      for model in model_list["models"]:
        base_url, token, model_name = model['base_url'], model['token'], model['model_name']

        benchmarks_results[file_names][model_name] = {}

        bert_results_general_query = BenchMarking.bertScore([meeting_json['general_query_list'][0][f'answer_{model_name}']], [meeting_json['general_query_list'][0]['answer']])['f1'][0]

        targets = []
        predictions = []
        for specific_query in meeting_json['specific_query_list']:
          targets.append(specific_query[f'answer'])
          predictions.append(specific_query[f'answer_{model_name}'])
        bert_results_specific_query = BenchMarking.bertScore(predictions, targets)['f1']
        bert_results_specific_query = sum(bert_results_specific_query) / len(bert_results_specific_query)
        benchmarks_results[file_names][model_name]['bertscore'] = {'general_query': bert_results_general_query, 'specific_query_avg': bert_results_specific_query}

        print(bert_results_general_query, bert_results_specific_query)
        factcc_results_general_query = json.loads(BenchMarking.LLMAsJudgeScore([meeting_json['general_query_list'][0][f'answer_{model_name}']], [meeting_json['general_query_list'][0]['answer']], base_url, token, model_name))
        print(factcc_results_general_query)
        factcc_results_specific_query = {"factuality": 0, "completeness": 0, "conciseness": 0}
        for specific_query in meeting_json['specific_query_list']:
          factcc_results_interm_specific_query = json.loads(BenchMarking.LLMAsJudgeScore(specific_query[f'answer_{model_name}'], specific_query[f'answer'], base_url, token, model_name))
          factcc_results_specific_query['factuality'] += factcc_results_interm_specific_query['factuality'] / len(meeting_json['specific_query_list'])
          factcc_results_specific_query['completeness'] += factcc_results_interm_specific_query['completeness'] / len(meeting_json['specific_query_list'])
          factcc_results_specific_query['conciseness'] += factcc_results_interm_specific_query['conciseness'] / len(meeting_json['specific_query_list'])

        print(factcc_results_specific_query)
        benchmarks_results[file_names][model_name]['llmasjudge'] = {'general_query': factcc_results_general_query, 'specific_query_avg': factcc_results_specific_query}

    with open(benchmarks_results_json_path, mode='w', encoding='utf-8') as json_f:
      json.dump(benchmarks_results, json_f, ensure_ascii=False, indent=2) #Making one big commit to main file

  @staticmethod
  def bertScore(predict, target):
    bertscore = load("bertscore")
    results = bertscore.compute(
        predictions=predict,
        references=target,
        model_type="bert-base-multilingual-cased",
        lang='ru',
        device='cuda',
        batch_size=8,
    )

    del bertscore
    gc.collect()
    torch.cuda.empty_cache()

    return results


  @staticmethod
  def LLMAsJudgeScore(predict, target, base_url, token, model_name):
    prompt = f'''
Ты — строгий фактолог. Твоя задача — проверить, насколько подтверждается ответ нейросети по тексту от оригинального ответа по тексту.

Оцени по трём критериям (от 1 до 5):

1. Фактологическая точность: насколько суммаризация соответствует исходному тексту?
2. Полнота: охвачены ли ключевые моменты?
3. Лаконичность: нет ли лишней информации?

Оригинальный ответ по тексту: {target}
Ответ от нейросети: {predict}

Ответ в формате JSON (это всего лишь пример):
{{"factuality": , "completeness": , "conciseness": }}
ВЫВОДИ ТОЛЬКО ЭТОТ ОТВЕТ В ФОРМАТЕ JSON, НИКАКИХ ПОЯСНЕНИЙ НЕ НУЖНО
'''
    print(token)
    llm_as_judge = summarize_with_openai(prompt=prompt, model=model_name, max_tokens=2000, base_url=base_url, openai_api_key=token)
    print(llm_as_judge)
    return llm_as_judge
 
models = {} #сюда свои модели токены
'''
{
"models": [
{
  "base_url":
  "token":
  "model_name":
},
{
  "base_url":
  "token":
  "model_name":
},
]
}
'''

for model in models["models"]:
  base_url, token, model_name = model['base_url'], model['token'], model['model_name']
  print(base_url, token, model_name)
  specific = AnsweringQuestions.answer('dataset_json.json', model_name, base_url, token)

BenchMarking.benchmark('bench_res.json', 'dataset_json.json', model_list=models)