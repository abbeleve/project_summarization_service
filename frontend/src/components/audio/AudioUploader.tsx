import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  SUPPORTED_FORMATS,
  TRANSCRIBE_CONFIG,
  DIARIZATION_CONFIG,
  LLM_MODELS,
  getTranscribeModelsByLib,
  getDiarizationModelsByLib,
  TRANSCRIBE_MODEL_DESCRIPTIONS,
  DIARIZATION_MODEL_DESCRIPTIONS,
  LLM_MODEL_DESCRIPTIONS
} from '@/config/settings';
import { type ProcessingSettings } from '@/types/transcript';
import { Button } from '@/components/ui/Button';
import { NoiseSuppressionToggle } from './NoiseSuprressionToggle';

interface AudioUploaderProps {
  onProcess: (file: File, settings: ProcessingSettings) => void;
  isProcessing: boolean;
  onNoiseSuppression?: (file: File) => Promise<Blob | null>;
}

/** Тип для идентификатора тултипа */
type TooltipId = 'transcribeLib' | 'transcribeModel' | 'diarizeLib' | 'diarizationModel' | 'llmModel' | null;

/** Компонент тултипа с информацией о модели */
const ModelTooltip = ({ 
  content,
  isVisible
}: { 
  content: React.ReactNode;
  isVisible: boolean;
}) => {
  if (!isVisible) return null;
  
  return (
    <div className="absolute top-full left-0 mt-2 z-50 min-w-[280px] max-w-[320px]">
      <div className="bg-gray-900 text-white text-sm rounded-xl p-4 shadow-2xl border border-gray-700">
        {content}
        {/* Стрелочка вверх */}
        <div className="absolute -top-1 left-4 w-3 h-3 bg-gray-900 border-l border-t border-gray-700 transform rotate-45"></div>
      </div>
    </div>
  );
};

export const AudioUploader = ({
  onProcess,
  isProcessing,
  onNoiseSuppression
}: AudioUploaderProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [denoisedFile, setDenoisedFile] = useState<Blob | null>(null);
  const [isDenoising, setIsDenoising] = useState(false);
  const [activeTooltip, setActiveTooltip] = useState<TooltipId>(null);
  const [settings, setSettings] = useState<ProcessingSettings>({
    transcribeModel: 'v3_ctc',
    diarizationModel: 'pyannote/speaker-diarization-community-1',
    diarizeLib: 'pyannote',
    transcribeLib: 'gigaam',
    llmModel: 'arcee-ai/trinity-mini:free',
    noiseSuppression: false
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles[0]) {
      setFile(acceptedFiles[0]);
      setDenoisedFile(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': SUPPORTED_FORMATS.map(ext => `.${ext}`),
      'video/mp4': ['.mp4']
    },
    multiple: false,
    disabled: isProcessing
  });

  const handleDenoise = async () => {
    if (!file || !onNoiseSuppression) return;
    
    setIsDenoising(true);
    try {
      const result = await onNoiseSuppression(file);
      if (result) {
        setDenoisedFile(result);
      }
    } finally {
      setIsDenoising(false);
    }
  };

  const handleSubmit = () => {
    if (file) {
      const fileToProcess = settings.noiseSuppression && denoisedFile
        ? new File([denoisedFile], `denoised_${file.name}`, { type: 'audio/wav' })
        : file;
      onProcess(fileToProcess, settings);
    }
  };

  const canProcess = file && (!settings.noiseSuppression || denoisedFile);
  const needsDenoising = settings.noiseSuppression && !denoisedFile;

  return (
    <div className="space-y-6">
      {/* Dropzone с градиентом */}
      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-300
          ${isDragActive 
            ? 'border-violet-500 bg-gradient-to-br from-violet-50 to-purple-50 scale-[1.02]' 
            : 'border-gray-300 hover:border-violet-400 hover:bg-gray-50'}
          ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
          ${!file ? 'bg-gradient-to-br from-gray-50 to-white' : 'bg-white'}
        `}
      >
        <input {...getInputProps()} />
        
        {/* Иконка */}
        <div className="flex justify-center mb-4">
          <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
            isDragActive 
              ? 'bg-violet-500 scale-110' 
              : 'bg-gradient-to-br from-violet-400 to-purple-500'
          }`}>
            <span className="text-3xl">🎵</span>
          </div>
        </div>
        
        <p className={`text-lg font-medium mb-2 ${
          isDragActive ? 'text-violet-700' : 'text-gray-700'
        }`}>
          {isDragActive ? 'Отпустите файл здесь...' : 'Перетащите аудиофайл или кликните для выбора'}
        </p>
        <p className="text-sm text-gray-500">
          Поддерживаемые форматы: <span className="font-medium text-gray-700">{SUPPORTED_FORMATS.join(', ')}</span>
        </p>
      </div>

      {/* Выбранный файл */}
      {file && (
        <div className="bg-gradient-to-r from-violet-50 to-purple-50 rounded-2xl p-5 border border-violet-200">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3 flex-1">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
                <span className="text-2xl">🎵</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900 truncate">{file.name}</p>
                <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
            <button
              onClick={() => { setFile(null); setDenoisedFile(null); }}
              className="w-8 h-8 rounded-full bg-white hover:bg-red-50 flex items-center justify-center transition-colors text-gray-400 hover:text-red-500 shadow-sm"
              disabled={isProcessing}
            >
              <span className="text-lg">×</span>
            </button>
          </div>

          {/* Аудио превью */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <p className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <span>🎧</span> Оригинал
              </p>
              <audio controls className="w-full" src={URL.createObjectURL(file)} />
            </div>

            {denoisedFile && (
              <div className="bg-white rounded-xl p-4 border border-green-200">
                <p className="text-sm font-medium text-green-700 mb-2 flex items-center gap-2">
                  <span>✨</span> С шумоподавлением
                </p>
                <audio controls className="w-full" src={URL.createObjectURL(denoisedFile)} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Noise suppression */}
      {file && onNoiseSuppression && (
        <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-2xl p-5 border border-emerald-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-md">
                <span className="text-xl">🔇</span>
              </div>
              <NoiseSuppressionToggle
                enabled={settings.noiseSuppression}
                onChange={(enabled) => setSettings(s => ({ ...s, noiseSuppression: enabled }))}
                disabled={isProcessing}
              />
            </div>

            {!denoisedFile && (
              <Button
                size="sm"
                onClick={handleDenoise}
                isLoading={isDenoising}
                disabled={isProcessing}
                className="bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600"
              >
                🎧 Обработать от шума
              </Button>
            )}
          </div>

          {denoisedFile && (
            <div className="flex items-center gap-2 text-sm text-emerald-700 bg-white/70 backdrop-blur p-3 rounded-xl border border-emerald-100">
              <span className="text-lg">✅</span>
              <span className="font-medium">Файл обработан</span>
              <button
                onClick={() => setDenoisedFile(null)}
                className="text-red-600 hover:text-red-800 ml-auto font-medium"
              >
                Сбросить
              </button>
            </div>
          )}
        </div>
      )}

      {/* Settings - аккордеон */}
      <details className="group border border-gray-200 rounded-2xl overflow-visible bg-white">
        <summary className="flex items-center gap-3 font-semibold cursor-pointer p-4 bg-gradient-to-r from-slate-50 to-gray-50 hover:from-slate-100 hover:to-gray-100 transition-colors">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-400 to-gray-500 flex items-center justify-center shadow-md">
            <span className="text-lg">⚙️</span>
          </div>
          <span className="text-lg text-gray-900">Настройки моделей</span>
          <span className="ml-auto text-gray-400 group-open:rotate-180 transition-transform">▼</span>
        </summary>
        <div className="p-5 space-y-4">
          {/* Информационное сообщение */}
          <div className="bg-gradient-to-r from-rose-50 to-pink-50 border border-rose-200 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-400 to-pink-500 flex items-center justify-center flex-shrink-0 shadow-sm">
                <span className="text-lg">💡</span>
              </div>
              <div className="flex-1">
                <p className="font-semibold text-rose-800 mb-1">Важная информация</p>
                <p className="text-sm text-rose-700 leading-relaxed">
                  Выбирайте модели вручную только в редких случаях: если вас не устраивает результат транскрибации или язык записи отличается от русского. 
                  <span className="font-medium"> По умолчанию используются оптимальные настройки.</span>
                </p>
              </div>
            </div>
          </div>
          
          {/* Пояснения терминов */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-gradient-to-br from-violet-50 to-purple-50 border border-violet-200 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">📝</span>
                <span className="font-semibold text-violet-800 text-sm">Транскрибация</span>
              </div>
              <p className="text-xs text-violet-700 leading-relaxed">
                Преобразование речи в текст. Модель «слышит» аудио и записывает слова.
              </p>
            </div>
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">👥</span>
                <span className="font-semibold text-blue-800 text-sm">Диаризация</span>
              </div>
              <p className="text-xs text-blue-700 leading-relaxed">
                Разделение спикеров. Определяет кто и когда говорил (Спикер 1, Спикер 2 и т.д.).
              </p>
            </div>
            <div className="bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">🤖</span>
                <span className="font-semibold text-amber-800 text-sm">LLM (суммаризация)</span>
              </div>
              <p className="text-xs text-amber-700 leading-relaxed">
                Нейросеть для создания краткого содержания. Превращает длинный текст в сжатый пересказ.
              </p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Транскрибация */}
          <div className="space-y-1">
            <label className="block text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span className="w-1 h-4 bg-violet-500 rounded-full"></span>
              Библиотека транскрибации
            </label>
            <div className="relative">
              <ModelTooltip
                isVisible={activeTooltip === 'transcribeLib'}
                content={
                  <>
                    <div className="font-semibold text-white border-b border-gray-700 pb-2 mb-2">
                      Сравнение библиотек
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="bg-violet-900/50 p-2 rounded-lg">
                        <div className="font-semibold text-violet-300">🎯 GigaAM (Сбер)</div>
                        <div className="text-gray-300 mt-1">{TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.description}</div>
                        <div className="mt-2 space-y-1">
                          <div>{TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.language}</div>
                          <div>{TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.speed}</div>
                          <div>{TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.size}</div>
                        </div>
                      </div>
                      <div className="bg-blue-900/50 p-2 rounded-lg">
                        <div className="font-semibold text-blue-300">🌍 Whisper (OpenAI)</div>
                        <div className="text-gray-300 mt-1">{TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.description}</div>
                        <div className="mt-2 space-y-1">
                          <div>{TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.language}</div>
                          <div>{TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.speed}</div>
                          <div>{TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.size}</div>
                        </div>
                      </div>
                    </div>
                  </>
                }
              />
              <select
                value={settings.transcribeLib}
                onChange={(e) => setSettings(s => ({ ...s, transcribeLib: e.target.value }))}
                onMouseEnter={() => setActiveTooltip('transcribeLib')}
                onMouseLeave={() => setActiveTooltip(null)}
                className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white hover:border-violet-300 cursor-help"
                disabled={isProcessing}
              >
                {Object.keys(TRANSCRIBE_CONFIG).map(lib => (
                  <option key={lib} value={lib}>{lib}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span className="w-1 h-4 bg-violet-500 rounded-full"></span>
              Модель транскрибации
              <span className="text-xs text-gray-400 font-normal">(наведите для деталей)</span>
            </label>
            <div className="relative">
              <ModelTooltip
                isVisible={activeTooltip === 'transcribeModel'}
                content={
                  <>
                    <div className="font-semibold text-white border-b border-gray-700 pb-2 mb-2">
                      {settings.transcribeLib === 'gigaam'
                        ? '🎯 GigaAM - Детали модели'
                        : '🌍 Whisper - Детали модели'
                      }
                    </div>
                    <div className="text-gray-300 text-xs">
                      {settings.transcribeLib === 'gigaam'
                        ? TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.description
                        : TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.description
                      }
                    </div>
                    <div className="space-y-1 text-xs mt-2">
                      <div><span className="text-gray-400">Язык:</span> {settings.transcribeLib === 'gigaam' ? TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.language : TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.language}</div>
                      <div><span className="text-gray-400">Скорость:</span> {settings.transcribeLib === 'gigaam' ? TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.speed : TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.speed}</div>
                      <div><span className="text-gray-400">Размер:</span> {settings.transcribeLib === 'gigaam' ? TRANSCRIBE_MODEL_DESCRIPTIONS.gigaam.size : TRANSCRIBE_MODEL_DESCRIPTIONS.whisper.size}</div>
                    </div>
                  </>
                }
              />
              <select
                value={settings.transcribeModel}
                onChange={(e) => setSettings(s => ({ ...s, transcribeModel: e.target.value }))}
                onMouseEnter={() => setActiveTooltip('transcribeModel')}
                onMouseLeave={() => setActiveTooltip(null)}
                className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white hover:border-violet-300 cursor-help"
                disabled={isProcessing}
              >
                {getTranscribeModelsByLib(settings.transcribeLib).map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Диаризация */}
          <div className="space-y-1">
            <label className="block text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span className="w-1 h-4 bg-blue-500 rounded-full"></span>
              Библиотека диаризации
            </label>
            <div className="relative">
              <ModelTooltip
                isVisible={activeTooltip === 'diarizeLib'}
                content={
                  <>
                    <div className="font-semibold text-white border-b border-gray-700 pb-2 mb-2">
                      🎙️ Pyannote - Диаризация спикеров
                    </div>
                    <div className="text-gray-300 text-xs">
                      Популярная open-source библиотека для определения и разделения спикеров в аудио.
                    </div>
                    <div className="space-y-1 text-xs mt-2">
                      <div>⭐ <span className="text-gray-400">Точность:</span> Высокая</div>
                      <div>🚀 <span className="text-gray-400">Скорость:</span> Средняя</div>
                      <div>📦 <span className="text-gray-400">Лицензия:</span> MIT</div>
                    </div>
                  </>
                }
              />
              <select
                value={settings.diarizeLib}
                onChange={(e) => setSettings(s => ({ ...s, diarizeLib: e.target.value }))}
                onMouseEnter={() => setActiveTooltip('diarizeLib')}
                onMouseLeave={() => setActiveTooltip(null)}
                className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-white hover:border-blue-300 cursor-help"
                disabled={isProcessing}
              >
                {Object.keys(DIARIZATION_CONFIG).map(lib => (
                  <option key={lib} value={lib}>{lib}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span className="w-1 h-4 bg-blue-500 rounded-full"></span>
              Модель диаризации
              <span className="text-xs text-gray-400 font-normal">(наведите для деталей)</span>
            </label>
            <div className="relative">
              <ModelTooltip
                isVisible={activeTooltip === 'diarizationModel'}
                content={
                  <>
                    <div className="font-semibold text-white border-b border-gray-700 pb-2 mb-2">
                      🎯 Детали модели
                    </div>
                    <div className="text-gray-300 text-xs">
                      {DIARIZATION_MODEL_DESCRIPTIONS[settings.diarizationModel]?.description || 'Модель для определения спикеров'}
                    </div>
                    <div className="space-y-1 text-xs mt-2">
                      <div><span className="text-gray-400">Точность:</span> {DIARIZATION_MODEL_DESCRIPTIONS[settings.diarizationModel]?.accuracy || '⭐⭐⭐⭐'}</div>
                      <div><span className="text-gray-400">Скорость:</span> {DIARIZATION_MODEL_DESCRIPTIONS[settings.diarizationModel]?.speed || '🚀 Средняя'}</div>
                    </div>
                  </>
                }
              />
              <select
                value={settings.diarizationModel}
                onChange={(e) => setSettings(s => ({ ...s, diarizationModel: e.target.value }))}
                onMouseEnter={() => setActiveTooltip('diarizationModel')}
                onMouseLeave={() => setActiveTooltip(null)}
                className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-white hover:border-blue-300 cursor-help"
                disabled={isProcessing}
              >
                {getDiarizationModelsByLib(settings.diarizeLib).map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Суммаризация */}
          <div className="space-y-1 md:col-span-2">
            <label className="block text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span className="w-1 h-4 bg-amber-500 rounded-full"></span>
              Модель LLM
              <span className="text-xs text-gray-400 font-normal">(наведите для деталей)</span>
            </label>
            <div className="relative">
              <ModelTooltip
                isVisible={activeTooltip === 'llmModel'}
                content={
                  <>
                    <div className="font-semibold text-white border-b border-gray-700 pb-2 mb-2">
                      🤖 Детали LLM модели
                    </div>
                    <div className="text-gray-300 text-xs">
                      {LLM_MODEL_DESCRIPTIONS[settings.llmModel]?.description || 'Модель для суммаризации текста'}
                    </div>
                    <div className="space-y-1 text-xs mt-2">
                      <div><span className="text-gray-400">Скорость:</span> {LLM_MODEL_DESCRIPTIONS[settings.llmModel]?.speed || '🚀 Быстрая'}</div>
                      <div><span className="text-gray-400">Контекст:</span> {LLM_MODEL_DESCRIPTIONS[settings.llmModel]?.context || '📝 Стандартный'}</div>
                    </div>
                  </>
                }
              />
              <select
                value={settings.llmModel}
                onChange={(e) => setSettings(s => ({ ...s, llmModel: e.target.value }))}
                onMouseEnter={() => setActiveTooltip('llmModel')}
                onMouseLeave={() => setActiveTooltip(null)}
                className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all bg-white hover:border-amber-300 cursor-help"
                disabled={isProcessing}
              >
                {LLM_MODELS.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>
          </div>
        </div>
      </details>

      {/* Кнопка анализа */}
      <button
        onClick={handleSubmit}
        disabled={!canProcess || isProcessing}
        className={`w-full py-4 px-6 rounded-2xl font-semibold text-lg transition-all duration-300 shadow-lg hover:shadow-xl ${
          canProcess && !isProcessing
            ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white hover:from-violet-700 hover:to-purple-700 hover:scale-[1.02]'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
      >
        {isProcessing ? (
          <span className="flex items-center justify-center gap-3">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Обработка...
          </span>
        ) : needsDenoising ? (
          <span className="flex items-center justify-center gap-2">
            ⚠️ Сначала обработайте файл от шума
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            🚀 Начать анализ
          </span>
        )}
      </button>
    </div>
  );
};