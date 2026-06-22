import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  SUPPORTED_FORMATS,
  TRANSCRIBE_CONFIG,
  DIARIZATION_CONFIG,
  LLM_MODELS,
  DEFAULT_SETTINGS,
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
  initialFile?: File | null;
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
  onNoiseSuppression,
  initialFile
}: AudioUploaderProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [denoisedFile, setDenoisedFile] = useState<Blob | null>(null);
  const [isDenoising, setIsDenoising] = useState(false);
  const [activeTooltip, setActiveTooltip] = useState<TooltipId>(null);
  const [title, setTitle] = useState('');

  // Предзагрузка файла из внешнего источника (drag-n-drop на тайл)
  useEffect(() => {
    if (initialFile) {
      setFile(initialFile);
      setDenoisedFile(null);
      setTitle('');
    }
  }, [initialFile]);

  const [settings, setSettings] = useState<ProcessingSettings>(() => {
    try {
      const saved = localStorage.getItem('modelSettings');
      return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles[0]) {
      setFile(acceptedFiles[0]);
      setDenoisedFile(null);
      setTitle('');
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
      onProcess(fileToProcess, { ...settings, meetingTitle: title || undefined });
      setFile(null);
      setDenoisedFile(null);
      setTitle('');
    }
  };

  const canProcess = file && (!settings.noiseSuppression || denoisedFile);
  const needsDenoising = settings.noiseSuppression && !denoisedFile;

  return (
    <div className="space-y-6">
      {!file ? (
        /* Dropzone — only when no file */
        <div
          {...getRootProps()}
          className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-300
            ${isDragActive
              ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-blue-50 dark:from-blue-900/20 dark:to-blue-900/20 scale-[1.02]'
              : 'border-gray-300 dark:border-dark-base-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-dark-base-800'}
            ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
            bg-gradient-to-br from-gray-50 to-white dark:from-dark-base-800 dark:to-dark-base-900
          `}
        >
          <input {...getInputProps()} />

          {/* Иконка */}
          <div className="flex justify-center mb-4">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
              isDragActive
                ? 'bg-blue-500 scale-110'
                : 'bg-gradient-to-br from-blue-400 to-blue-500'
            }`}>
              <span className="text-3xl">🎤</span>
            </div>
          </div>

          <p className={`text-lg font-medium mb-2 ${
            isDragActive ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'
          }`}>
            {isDragActive ? 'Отпустите файл здесь...' : 'Перетащите аудиофайл или кликните для выбора'}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Поддерживаемые форматы: <span className="font-medium text-gray-700 dark:text-gray-300">{SUPPORTED_FORMATS.join(', ')}</span>
          </p>
        </div>
      ) : (
        /* File info + player — replaces dropzone when file loaded */
        <div className="bg-gradient-to-br from-gray-50 to-white dark:from-dark-base-800 dark:to-dark-base-900 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3 flex-1">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                <span className="text-2xl">🎤</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900 dark:text-white truncate">{file.name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
            <button
              onClick={() => { setFile(null); setDenoisedFile(null); setTitle(''); }}
              className="w-8 h-8 rounded-full bg-white dark:bg-dark-base-800 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center justify-center transition-colors text-gray-400 hover:text-red-500 shadow-sm"
              disabled={isProcessing}
            >
              <span className="text-lg">×</span>
            </button>
          </div>

          {/* Аудио превью */}
          <div className="space-y-4">
            <div className="bg-white dark:bg-dark-base-800 rounded-xl p-4 border border-gray-200 dark:border-dark-base-700">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                <span>🎧</span> Оригинал
              </p>
              <audio controls className="w-full" src={URL.createObjectURL(file)} />
            </div>

            {denoisedFile && (
              <div className="bg-white dark:bg-dark-base-800 rounded-xl p-4 border border-green-200 dark:border-green-800">
                <p className="text-sm font-medium text-green-700 dark:text-green-400 mb-2 flex items-center gap-2">
                  <span>✨</span> С шумоподавлением
                </p>
                <audio controls className="w-full" src={URL.createObjectURL(denoisedFile)} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Meeting title input */}
      {file && (
        <div className="bg-gradient-to-br from-gray-50 to-white dark:from-dark-base-800 dark:to-dark-base-900 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700">
          <label className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center shadow-md shrink-0">
              <span className="text-lg">📋</span>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Название совещания</p>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Не указано (будет определено автоматически)"
                disabled={isProcessing}
                className="w-full bg-white dark:bg-dark-base-800 border border-gray-300 dark:border-dark-base-600 rounded-xl px-4 py-2.5 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-400 focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent transition-all disabled:opacity-50"
              />
            </div>
          </label>
        </div>
      )}

      {/* Noise suppression */}
      {file && onNoiseSuppression && (
        <div className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 rounded-2xl p-5 border border-emerald-200 dark:border-emerald-800">
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
            <div className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400 bg-white/70 dark:bg-dark-base-800/70 backdrop-blur p-3 rounded-xl border border-emerald-100 dark:border-emerald-800">
              <span className="text-lg">✅</span>
              <span className="font-medium">Файл обработан</span>
              <button
                onClick={() => setDenoisedFile(null)}
                className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 ml-auto font-medium"
              >
                Сбросить
              </button>
            </div>
          )}
        </div>
      )}

      {/* Кнопка анализа */}
      <button
        onClick={handleSubmit}
        disabled={!canProcess || isProcessing}
        className={`w-full py-4 px-6 rounded-2xl font-semibold text-lg transition-all duration-300 shadow-lg hover:shadow-xl ${
          canProcess && !isProcessing
            ? 'bg-gradient-to-r from-blue-600 to-blue-600 text-white hover:from-blue-700 hover:to-blue-700 hover:scale-[1.02]'
            : 'bg-gray-200 dark:bg-dark-base-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
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
