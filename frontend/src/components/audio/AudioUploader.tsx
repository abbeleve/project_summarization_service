import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { SUPPORTED_FORMATS, DEFAULT_SETTINGS } from '@/config/settings';
import { type ProcessingSettings } from '@/types/transcript';
import { NoiseSuppressionToggle } from './NoiseSuprressionToggle';

interface AudioUploaderProps {
  onProcess: (file: File, settings: ProcessingSettings) => void;
  isProcessing: boolean;
  onNoiseSuppression?: (file: File) => Promise<Blob | null>;
  initialFile?: File | null;
}

export const AudioUploader = ({
  onProcess,
  isProcessing,
  onNoiseSuppression,
  initialFile
}: AudioUploaderProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [denoisedFile, setDenoisedFile] = useState<Blob | null>(null);
  const [isDenoising, setIsDenoising] = useState(false);
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

  const formatSize = (bytes: number) => {
    const mb = bytes / 1024 / 1024;
    return `${mb.toFixed(2)} MB`;
  };

  return (
    <div className="space-y-5">
      {!file ? (
        /* ── Dropzone ── */
        <div
          {...getRootProps()}
          className={`
            relative rounded-[14px] p-14 text-center cursor-pointer
            transition-all duration-300 select-none
            ${!isDragActive ? 'dropzone-idle' : ''}
            ${isDragActive
              ? 'bg-gradient-to-b from-blue-500/10 to-transparent border-[1.5px] border-dashed border-blue-500/50 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.15),0_0_50px_rgba(59,130,246,0.05)]'
              : 'surface-base hover:bg-gray-50 dark:hover:bg-[#28282c]'}
            ${isProcessing ? 'opacity-40 cursor-not-allowed' : ''}
          `}
        >
          <input {...getInputProps()} />

          {/* Внутренний halo-круг (только в idle) */}
          {!isDragActive && (
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[200px] h-[200px] rounded-full bg-blue-500/5 pointer-events-none" />
          )}

          {/* Иконка */}
          <div className="flex justify-center mb-5">
            <div className={`
              w-[60px] h-[60px] rounded-[16px] flex items-center justify-center
              transition-all duration-300
              ${isDragActive
                ? 'bg-blue-500 scale-105 shadow-[0_0_30px_-4px_rgba(59,130,246,0.4)]'
                : 'bg-gradient-to-br from-blue-500 to-blue-700 shadow-[0_8px_24px_-8px_rgba(59,130,246,0.4)]'}
            `}>
              <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </div>
          </div>

          <p className="text-base font-medium text-gray-900 dark:text-[#f5f5f7] mb-1.5">
            {isDragActive ? 'Отпустите файл для загрузки' : 'Перетащите аудиофайл или нажмите для выбора'}
          </p>
          <p className="text-xs text-gray-400 dark:text-[#6b6b75] tracking-[0.01em]">
            Поддерживаемые форматы: <span className="text-gray-500 dark:text-[#a0a0a8] font-medium">{SUPPORTED_FORMATS.join(', ')}</span>
          </p>
        </div>
      ) : (
        /* ── File info + player — replaces dropzone when file loaded ── */
        <div className="surface-base p-5">
          <div className="flex items-start justify-between mb-5">
            <div className="flex items-center gap-3.5 flex-1 min-w-0">
              {/* Document thumbnail */}
              <div className="relative w-11 h-11 rounded-[10px] bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0 shadow-[0_4px_16px_-4px_rgba(59,130,246,0.4)]">
                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-[#f5f5f7] truncate">{file.name}</p>
                <p className="tabular text-xs text-gray-400 dark:text-[#6b6b75] mt-0.5">{formatSize(file.size)}</p>
              </div>
            </div>
            <button
              onClick={() => { setFile(null); setDenoisedFile(null); setTitle(''); }}
              className="w-7 h-7 rounded-[8px] surface-base flex items-center justify-center text-gray-400 dark:text-[#6b6b75] hover:text-red-400 hover:bg-red-500/10 transition-colors"
              disabled={isProcessing}
              aria-label="Удалить файл"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* Audio previews */}
          <div className="space-y-3">
            <div className="surface-base p-3.5">
              <p className="text-[11px] font-medium text-gray-400 dark:text-[#6b6b75] uppercase tracking-[0.08em] mb-3">Оригинал</p>
              <audio controls className="w-full" src={URL.createObjectURL(file)} />
            </div>

            {denoisedFile && (
              <div className="surface-base p-3.5">
                <p className="text-[11px] font-medium text-blue-400 uppercase tracking-[0.08em] mb-3">С шумоподавлением</p>
                <audio controls className="w-full" src={URL.createObjectURL(denoisedFile)} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Meeting title input ── */}
      {file && (
        <div className="surface-base p-5">
          <label className="block">
            <p className="text-[11px] font-medium text-gray-400 dark:text-[#6b6b75] uppercase tracking-[0.08em] mb-2">Название совещания</p>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Не указано (будет определено автоматически)"
              disabled={isProcessing}
              className="
                w-full bg-transparent px-0 py-2
                text-sm text-gray-900 dark:text-[#f5f5f7] placeholder-gray-400 dark:placeholder-[#6b6b75]/60
                border-b border-gray-200 dark:border-[rgba(255,255,255,0.06)]
                focus:border-blue-500 focus:outline-none
                transition-colors duration-200
                disabled:opacity-40
              "
            />
          </label>
        </div>
      )}

      {/* ── Noise suppression ── */}
      {file && onNoiseSuppression && (
        <div className="surface-base p-5">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-[10px] bg-gradient-to-br from-blue-500/20 to-blue-700/20 flex items-center justify-center shrink-0 border border-[rgba(59,130,246,0.15)]">
                <svg className="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                  <line x1="2" y1="2" x2="22" y2="22" />
                </svg>
              </div>
              <NoiseSuppressionToggle
                enabled={settings.noiseSuppression}
                onChange={(enabled) => setSettings(s => ({ ...s, noiseSuppression: enabled }))}
                disabled={isProcessing}
              />
            </div>

            {!denoisedFile && (
              <button
                onClick={handleDenoise}
                disabled={isProcessing || isDenoising}
                className={`
                  inline-flex items-center gap-1.5 px-4 py-2 rounded-[8px] text-xs font-medium
                  transition-all duration-200 shrink-0
                  ${isDenoising || isProcessing
                    ? 'bg-[rgba(255,255,255,0.04)] text-[#6b6b75] cursor-not-allowed'
                    : 'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20'}
                `}
              >
                {isDenoising ? (
                  <>
                    <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Обработка...
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 18V5l12-2v13" />
                      <circle cx="6" cy="18" r="3" />
                      <circle cx="18" cy="16" r="3" />
                    </svg>
                    Обработать
                  </>
                )}
              </button>
            )}
          </div>

          {denoisedFile && (
            <div className="mt-3 flex items-center gap-2.5 px-3.5 py-2.5 rounded-[10px] bg-blue-500/10 border border-blue-500/20">
              <svg className="w-4 h-4 text-blue-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span className="text-xs text-gray-500 dark:text-[#a0a0a8]">Файл обработан — шумоподавление применено</span>
              <button
                onClick={() => setDenoisedFile(null)}
                className="ml-auto text-xs text-gray-400 dark:text-[#6b6b75] hover:text-red-400 transition-colors"
              >
                Сбросить
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Кнопка анализа ── */}
      <button
        onClick={handleSubmit}
        disabled={!canProcess || isProcessing}
        className={`
          relative w-full py-[15px] px-6 rounded-[12px]
          font-semibold text-[13px] tracking-[0.04em] uppercase
          transition-all duration-300 select-none
          ${canProcess && !isProcessing
            ? 'text-white cta-breathe cursor-pointer'
            : 'bg-gray-50 dark:bg-[rgba(255,255,255,0.03)] text-gray-400 dark:text-[#6b6b75] cursor-not-allowed'}
        `}
        style={canProcess && !isProcessing ? {
          background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
        } : undefined}
      >
        {/* Внутренний highlight (только active) */}
        {canProcess && !isProcessing && (
          <span
            className="absolute inset-0 rounded-[12px] pointer-events-none"
            style={{
              background: 'linear-gradient(180deg, rgba(255,255,255,0.12) 0%, transparent 55%)',
            }}
          />
        )}

        <span className="relative z-[1] flex items-center justify-center gap-2.5">
          {isProcessing ? (
            <>
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Обработка...
            </>
          ) : needsDenoising ? (
            <>
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              Требуется обработка шума
            </>
          ) : (
            <>
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Начать анализ
            </>
          )}
        </span>
      </button>
    </div>
  );
};
