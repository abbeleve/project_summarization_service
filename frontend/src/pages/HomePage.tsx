import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useActiveTasks } from '@/hooks/useActiveTasks';
import { AudioUploader } from '@/components/audio/AudioUploader';
import { ActiveTasksList } from '@/components/tasks/ActiveTasksList';
import { Pagination } from '@/components/ui/Pagination';
import { transcriptsApi } from '@/api/transcripts';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { type ProcessingSettings } from '@/types/transcript';

const TRANSCRIPTS_PER_PAGE = 20;

export const HomePage = () => {
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const { transcripts, isLoading, error, total, refetch, processAudio, deleteTranscript } = useTranscripts({
    limit: TRANSCRIPTS_PER_PAGE,
    offset
  });
  const { tasks, addTask, removeTask } = useActiveTasks();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);

  // Проверяем завершённые задачи и показываем уведомление
  useEffect(() => {
    const completedTask = tasks.find(t => t.status === 'completed' && t.result?.transcript_id);
    if (completedTask) {
      setTaskError(null);
      refetch();
    }
  }, [tasks, refetch]);

  const handleProcess = async (file: File, settings: ProcessingSettings) => {
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
  };

  const handleNoiseSuppression = async (file: File): Promise<Blob | null> => {
    try {
      const blob = await transcriptsApi.applyNoiseSuppression(file);
      return blob;
    } catch (err) {
      console.error('Noise suppression error:', err);
      return null;
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTranscript(id);
      setConfirmDelete(null);
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  return (
    <div className="space-y-8">
      {/* Upload section */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 mb-4">📤 Новый анализ</h2>
        <AudioUploader
          onProcess={handleProcess}
          isProcessing={false}
          onNoiseSuppression={handleNoiseSuppression}
        />
      </section>

      {/* Active tasks list */}
      {tasks.length > 0 && (
        <section>
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

      {/* History section */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 mb-4">📋 История транскрипций</h2>
        
        {isLoading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner text="Загрузка истории..." size={'sm'} />
          </div>
        ) : error ? (
          <ErrorMessage message="Не удалось загрузить историю" />
        ) : !transcripts?.length ? (
          <Card className="p-8 text-center text-gray-500">
            У вас пока нет транскрипций
          </Card>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-600">
                Показано {transcripts.length} из {total} транскрипций
              </p>
            </div>
            <div className="grid gap-4">
              {transcripts.map((transcript) => (
                <Card key={transcript.transcript_id} hover className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900">{transcript.title}</h3>

                      <div className="flex items-center gap-2 mt-1">
                        <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">
                          {transcript.meeting_type}
                        </span>
                        <span className="text-xs text-gray-500">
                          {format(new Date(transcript.created_at), 'dd.MM.yyyy HH:mm', { locale: ru })}
                        </span>
                      </div>

                      {transcript.key_points?.[0] && (
                        <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                          {transcript.key_points[0]}
                        </p>
                      )}

                      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                        <span>🗣️ {transcript.speakers?.length || 0} спикеров</span>
                        <span>⏱️ {(transcript.duration || 0 / 60).toFixed(1)} мин</span>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => navigate(`/analysis/${transcript.transcript_id}`)}
                      >
                        📊
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => setConfirmDelete(transcript.transcript_id)}
                      >
                        🗑️
                      </Button>
                    </div>
                  </div>

                  {/* Delete confirmation */}
                  {confirmDelete === transcript.transcript_id && (
                    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                      <p className="text-sm text-red-800 mb-2">Удалить эту транскрипцию?</p>
                      <div className="flex gap-2">
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDelete(transcript.transcript_id)}
                        >
                          Да, удалить
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setConfirmDelete(null)}
                        >
                          Отмена
                        </Button>
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>

            {/* Pagination */}
            <Pagination
              total={total}
              limit={TRANSCRIPTS_PER_PAGE}
              offset={offset}
              onPageChange={setOffset}
            />
          </div>
        )}
      </section>
    </div>
  );
};