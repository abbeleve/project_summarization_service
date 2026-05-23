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

  const handleProcess = useCallback(async (file: File, settings: ProcessingSettings) => {
    try {
      setTaskError(null);
      const result = await processAudio({ file, settings });

      // Проверяем, вернул ли backend task_id (очередь) или готовую транскрипцию
      if ('task_id' in result) {
        addTask(result.task_id);
        // Не блокируем интерфейс, просто добавляем задачу в список
      } else if ('transcript_id' in result) {
        navigate(`/analysis/${result.transcript_id}`);
      }
    } catch (err) {
      console.error('Processing error:', err);
      setTaskError(err instanceof Error ? err.message : 'Ошибка обработки');
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
    <div className="fixed inset-0 overflow-hidden">
      {/* Full-width background layers — fixed to viewport */}
      <div className="fixed inset-x-0 top-0 h-1/2 bg-[linear-gradient(135deg,#e5e7eb,#f3f4f6_30%,#ffffff_50%,#f3f4f6_70%,#e5e7eb)] dark:bg-[linear-gradient(135deg,#232326,#28282b_30%,#2d2d30_50%,#28282b_70%,#232326)] pointer-events-none z-0" />
      <div className="fixed inset-x-0 bottom-0 h-1/2 bg-gray-100 dark:bg-[#232326] pointer-events-none z-0" />

      {/* Content on top */}
      <div className="relative z-10 h-full flex flex-col">
        {/* Top half — fixed, no scroll */}
        <div className="flex-none h-1/2 pt-28 overflow-hidden">
          <div className="max-w-5xl mx-auto px-6">
            <div className="flex items-start justify-between gap-8">
            <div className="max-w-md">
              <h1 className="text-5xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight">Новый анализ</h1>
              <p className="text-base text-gray-500 dark:text-gray-300 mt-2 leading-relaxed">
                Загрузите аудио- или видеофайл для транскрибации и анализа встречи.
              </p>
              <p className="text-base text-gray-500 dark:text-gray-300 leading-relaxed">
                Поддерживаются множество аудио и видео форматов.
              </p>
            </div>

            {/* Pipeline diagram */}
            <div className="hidden sm:flex items-center gap-3 shrink-0 mt-6">
              <div className="flex flex-col items-center justify-center w-24 h-24 rounded-xl bg-gray-700 bg-opacity-100 shadow-lg">
                <svg className="w-9 h-9 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2Z" />
                  <polyline points="14 2 14 8 20 8" />
                  <path d="M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
                  <path d="m17 17-3-2.5-2 2-3-3-3 3.5" />
                </svg>
                <span className="text-sm font-medium text-white whitespace-nowrap mt-2">Файл</span>
              </div>
              <svg className="w-6 h-0.5 text-gray-300 dark:text-dark-base-600 shrink-0" viewBox="0 0 20 2" fill="currentColor">
                <rect x="0" y="0" width="20" height="2" rx="1" />
              </svg>
              <div className="relative flex items-center justify-center">
                <svg className="absolute w-72 h-72 text-gray-500/20 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.3" strokeDasharray="4 1.5">
                  <circle cx="12" cy="12" r="10" />
                </svg>
                <svg className="absolute w-44 h-44 text-gray-500/20 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.3" strokeDasharray="4 1.5">
                  <circle cx="12" cy="12" r="10" />
                </svg>
                <svg className="w-12 h-12 text-gray-400 shrink-0 relative" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
                </svg>
              </div>
              <svg className="w-6 h-0.5 text-gray-300 dark:text-dark-base-600 shrink-0" viewBox="0 0 20 2" fill="currentColor">
                <rect x="0" y="0" width="20" height="2" rx="1" />
              </svg>
              <div className="flex flex-col items-center justify-center w-24 h-24 rounded-xl bg-gray-700 bg-opacity-100 shadow-lg">
                <svg className="w-9 h-9 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2Z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="8" y1="13" x2="16" y2="13" />
                  <line x1="8" y1="17" x2="16" y2="17" />
                  <line x1="8" y1="9" x2="10" y2="9" />
                </svg>
                <span className="text-sm font-medium text-white whitespace-nowrap mt-2">Результат</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AudioUploader — fixed top anchor, grows downward */}
      <div className="absolute top-[calc(50%-140px)] left-1/2 -translate-x-1/2 z-20 w-full max-w-2xl px-6">
        <div className="w-full">
          <AudioUploader
          onProcess={handleProcess}
          isProcessing={false}
          onNoiseSuppression={handleNoiseSuppression}
          initialFile={droppedFile}
        />
      </div>
      </div>

      {/* Bottom half — scrolls internally */}
      <div className="flex-1 overflow-y-hidden pt-16">
        <div className="max-w-5xl mx-auto px-6">
          {/* Active tasks list */}
          {tasks.length > 0 && (
            <section>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-3">Активные задачи</h2>
              <ActiveTasksList
                tasks={tasks}
                onRemove={removeTask}
                onNavigate={(transcriptId) => navigate(`/analysis/${transcriptId}`)}
              />
            </section>
          )}

          {/* Task error */}
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
    </div>
  );
};
