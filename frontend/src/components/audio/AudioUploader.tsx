import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { 
  SUPPORTED_FORMATS, 
  TRANSCRIBE_CONFIG, 
  DIARIZATION_CONFIG, 
  LLM_MODELS,
  getTranscribeModelsByLib,
  getDiarizationModelsByLib
} from '@/config/settings';
import { type ProcessingSettings } from '@/types/transcript';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { NoiseSuppressionToggle } from './NoiseSuprressionToggle';

interface AudioUploaderProps {
  onProcess: (file: File, settings: ProcessingSettings) => void;
  isProcessing: boolean;
  onNoiseSuppression?: (file: File) => Promise<Blob | null>;
}

export const AudioUploader = ({ 
  onProcess, 
  isProcessing, 
  onNoiseSuppression 
}: AudioUploaderProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [denoisedFile, setDenoisedFile] = useState<Blob | null>(null);
  const [isDenoising, setIsDenoising] = useState(false);
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

  const canProcess = file && (!settings.noiseSuppression || denoisedFile || isDenoising);

  return (
    <Card className="space-y-6">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'}
          ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        <p className="text-gray-600">
          {isDragActive ? 'Отпустите файл здесь...' : 'Перетащите аудиофайл или кликните для выбора'}
        </p>
        <p className="text-sm text-gray-400 mt-2">
          Поддерживаемые форматы: {SUPPORTED_FORMATS.join(', ')}
        </p>
      </div>

      {/* Selected file info */}
      {file && (
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div>
            <p className="font-medium">{file.name}</p>
            <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
          <button
            onClick={() => { setFile(null); setDenoisedFile(null); }}
            className="text-red-500 hover:text-red-700"
            disabled={isProcessing}
          >
            ✕
          </button>
        </div>
      )}

      {/* Audio preview */}
      {file && (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">🎧 Оригинал</p>
            <audio controls className="w-full" src={URL.createObjectURL(file)} />
          </div>
          
          {denoisedFile && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">🎧 С шумоподавлением</p>
              <audio controls className="w-full" src={URL.createObjectURL(denoisedFile)} />
            </div>
          )}
        </div>
      )}

      {/* Noise suppression */}
      {file && onNoiseSuppression && (
        <div className="p-4 bg-gray-50 rounded-lg">
          <NoiseSuppressionToggle
            enabled={settings.noiseSuppression}
            onChange={(enabled) => setSettings(s => ({ ...s, noiseSuppression: enabled }))}
            disabled={isProcessing}
          />
          
          {settings.noiseSuppression && !denoisedFile && (
            <Button 
              size="sm" 
              onClick={handleDenoise} 
              isLoading={isDenoising}
              disabled={isProcessing}
            >
              Обработать
            </Button>
          )}
        </div>
      )}

      {/* Settings */}
      <details className="border rounded-lg" open>
        <summary className="font-medium cursor-pointer p-4 hover:bg-gray-50">⚙️ Настройки моделей</summary>
        <div className="p-4 pt-0 grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Транскрибация */}
          <div>
            <label className="block text-sm font-medium mb-1">Библиотека транскрибации</label>
            <select
              value={settings.transcribeLib}
              onChange={(e) => setSettings(s => ({ ...s, transcribeLib: e.target.value }))}
              className="w-full border rounded px-3 py-2"
              disabled={isProcessing}
            >
              {Object.keys(TRANSCRIBE_CONFIG).map(lib => (
                <option key={lib} value={lib}>{lib}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Модель транскрибации</label>
            <select
              value={settings.transcribeModel}
              onChange={(e) => setSettings(s => ({ ...s, transcribeModel: e.target.value }))}
              className="w-full border rounded px-3 py-2"
              disabled={isProcessing}
            >
              {getTranscribeModelsByLib(settings.transcribeLib).map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>

          {/* Диаризация */}
          <div>
            <label className="block text-sm font-medium mb-1">Библиотека диаризации</label>
            <select
              value={settings.diarizeLib}
              onChange={(e) => setSettings(s => ({ ...s, diarizeLib: e.target.value }))}
              className="w-full border rounded px-3 py-2"
              disabled={isProcessing}
            >
              {Object.keys(DIARIZATION_CONFIG).map(lib => (
                <option key={lib} value={lib}>{lib}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Модель диаризации</label>
            <select
              value={settings.diarizationModel}
              onChange={(e) => setSettings(s => ({ ...s, diarizationModel: e.target.value }))}
              className="w-full border rounded px-3 py-2"
              disabled={isProcessing}
            >
              {getDiarizationModelsByLib(settings.diarizeLib).map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>

          {/* Суммаризация */}
          <div>
            <label className="block text-sm font-medium mb-1">Модель LLM</label>
            <select
              value={settings.llmModel}
              onChange={(e) => setSettings(s => ({ ...s, llmModel: e.target.value }))}
              className="w-full border rounded px-3 py-2"
              disabled={isProcessing}
            >
              {LLM_MODELS.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>
        </div>
      </details>

      {/* Process button */}
      <Button
        onClick={handleSubmit}
        disabled={!canProcess || isProcessing}
        isLoading={isProcessing}
        fullWidth
        size="lg"
      >
        {isProcessing ? '🔄 Обработка...' : '🎯 Анализировать'}
      </Button>
    </Card>
  );
};