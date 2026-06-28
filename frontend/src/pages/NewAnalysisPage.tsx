import { useState, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useActiveTasks } from '@/hooks/useActiveTasks';
import { AudioUploader } from '@/components/audio/AudioUploader';
import { ActiveTasksList } from '@/components/tasks/ActiveTasksList';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { transcriptsApi } from '@/api/transcripts';
import { type ProcessingSettings } from '@/types/transcript';

export const NewAnalysisPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const droppedFile = (location.state as { droppedFile?: File } | null)?.droppedFile ?? null;

  const { processAudio } = useTranscripts({});
  const { tasks, addTask, removeTask } = useActiveTasks();
  const [taskError, setTaskError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  const handleProcess = useCallback(async (file: File, settings: ProcessingSettings) => {
    try {
      setTaskError(null);
      setProcessing(true);
      const result = await processAudio({ file, settings });

      if ('task_id' in result) {
        addTask(result.task_id);
      } else if ('transcript_id' in result) {
        navigate(`/analysis/${result.transcript_id}`);
      }
    } catch (err) {
      console.error('Processing error:', err);
      setTaskError(err instanceof Error ? err.message : 'Ошибка обработки');
    } finally {
      setProcessing(false);
    }
  }, [processAudio, navigate, addTask]);

  const handleNoiseSuppression = useCallback(async (file: File): Promise<Blob | null> => {
    try {
      const blob = await transcriptsApi.applyNoiseSuppression(file);
      return blob;
    } catch (err) {
      console.error('Noise suppression error:', err);
      return null;
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#232326]">
      <div className="mx-auto max-w-5xl px-6 pt-16 pb-20">
        {/* Hero header */}
        <div className="flex items-start justify-between gap-8">
          <div className="max-w-md">
            <p className="text-[11px] font-medium text-gray-400 dark:text-[#6b6b75] uppercase tracking-[0.12em] mb-2">
              Upload &amp; Transcribe
            </p>
            <h1 className="text-5xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight leading-[1.1]">
              Новый анализ
            </h1>
            <p className="text-sm text-gray-500 dark:text-[#a0a0a8] mt-3 leading-relaxed max-w-sm">
              Загрузите аудио- или видеофайл для транскрибации и анализа встречи.
              Поддерживаются множество аудио и видео форматов.
            </p>
          </div>

          {/* Pipeline diagram */}
          <div className="hidden sm:flex items-center gap-2 shrink-0 mt-8">
            <div className="flex flex-col items-center justify-center w-20 h-20 rounded-[12px] surface-base">
              <svg className="w-7 h-7 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2Z" />
                <polyline points="14 2 14 8 20 8" />
                <path d="M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
                <path d="m17 17-3-2.5-2 2-3-3-3 3.5" />
              </svg>
              <span className="text-[10px] font-medium text-gray-500 dark:text-[#a0a0a8] mt-1.5">Файл</span>
            </div>
            <div className="w-5 h-[1.5px] bg-gray-200 dark:bg-[rgba(255,255,255,0.08)] rounded-full" />
            <div className="relative flex items-center justify-center w-20 h-20">
              <svg className="absolute w-44 h-44 text-blue-500/5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.3">
                <circle cx="12" cy="12" r="10" />
              </svg>
              <svg className="absolute w-28 h-28 text-blue-500/3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.3">
                <circle cx="12" cy="12" r="10" />
              </svg>
              <svg className="w-8 h-8 text-blue-500/70 relative" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
              </svg>
            </div>
            <div className="w-5 h-[1.5px] bg-gray-200 dark:bg-[rgba(255,255,255,0.08)] rounded-full" />
            <div className="flex flex-col items-center justify-center w-20 h-20 rounded-[12px] surface-base">
              <svg className="w-7 h-7 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2Z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="8" y1="13" x2="16" y2="13" />
                <line x1="8" y1="17" x2="16" y2="17" />
                <line x1="8" y1="9" x2="10" y2="9" />
              </svg>
              <span className="text-[10px] font-medium text-gray-500 dark:text-[#a0a0a8] mt-1.5">Результат</span>
            </div>
          </div>
        </div>

        {/* AudioUploader — centered narrow column */}
        <div className="flex justify-center mt-12 z-20">
          <div className="w-full max-w-lg">
            <AudioUploader
              onProcess={handleProcess}
              isProcessing={processing}
              onNoiseSuppression={handleNoiseSuppression}
              initialFile={droppedFile}
            />
          </div>
        </div>

        {/* Processing overlay */}
        {processing && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center surface-glass">
            <div className="flex flex-col items-center gap-4">
              <svg className="animate-spin h-10 w-10 text-blue-500" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <p className="text-lg font-medium text-gray-900 dark:text-[#f5f5f7]">Обработка...</p>
              <p className="text-sm text-gray-500 dark:text-[#a0a0a8]">Пожалуйста, подождите</p>
            </div>
          </div>
        )}

        {/* Bottom — tasks */}
        <div className="mt-12">
          <section>
            {tasks.length > 0 ? (
              <ActiveTasksList
                tasks={tasks}
                onRemove={removeTask}
                onNavigate={(transcriptId) => navigate(`/analysis/${transcriptId}`)}
              />
            ) : (
              <div className="text-center py-12">
                <p className="text-sm text-gray-400 dark:text-[#6b6b75]">Нет активных задач</p>
              </div>
            )}
          </section>

          {taskError && (
            <section>
              <ErrorMessage
                message={`Ошибка обработки: ${taskError}`}
                onRetry={() => setTaskError(null)}
              />
            </section>
          )}
        </div>
      </div>
    </div>
  );
};
