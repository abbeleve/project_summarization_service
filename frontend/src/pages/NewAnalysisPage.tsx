import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useActiveTasks } from '@/hooks/useActiveTasks';
import { AudioUploader } from '@/components/audio/AudioUploader';
import { ActiveTasksList } from '@/components/tasks/ActiveTasksList';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { transcriptsApi } from '@/api/transcripts';
import { type ProcessingSettings } from '@/types/transcript';

export const NewAnalysisPage = () => {
  const navigate = useNavigate();
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
    <div className="space-y-8">
      {/* Hero section */}
      <section>
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center shadow-lg">
            <span className="text-2xl">📤</span>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Новый анализ</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Загрузите аудиофайл для транскрибации и анализа встречи
            </p>
          </div>
        </div>

        <AudioUploader
          onProcess={handleProcess}
          isProcessing={false}
          onNoiseSuppression={handleNoiseSuppression}
        />
      </section>

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
  );
};
