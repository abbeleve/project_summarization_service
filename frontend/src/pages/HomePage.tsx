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
      <section className="mt-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center shadow-lg">
            <span className="text-2xl">📋</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">История транскрипций</h2>
            <p className="text-sm text-gray-500">
              {total > 0 ? `Всего ${total} транскрипций` : 'Пока пусто'}
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner text="Загрузка истории..." size={'sm'} />
          </div>
        ) : error ? (
          <ErrorMessage message="Не удалось загрузить историю" />
        ) : !transcripts?.length ? (
          <Card className="p-12 text-center">
            <div className="max-w-md mx-auto">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center mx-auto mb-4">
                <span className="text-4xl">📝</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">У вас пока нет транскрипций</h3>
              <p className="text-gray-500 mb-6">
                Загрузите аудиофайл выше, чтобы начать анализ встречи
              </p>
            </div>
          </Card>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-600">
                Показано <span className="font-semibold text-gray-900">{transcripts.length}</span> из <span className="font-semibold text-gray-900">{total}</span> транскрипций
              </p>
            </div>
            <div className="grid gap-4">
              {transcripts.map((transcript) => (
                <div
                  key={transcript.transcript_id}
                  className="group bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-xl hover:border-violet-200 transition-all duration-300 cursor-pointer"
                  onClick={() => navigate(`/analysis/${transcript.transcript_id}`)}
                >
                  <div className="flex items-start gap-4">
                    {/* Иконка типа встречи */}
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm ${
                      transcript.meeting_type.includes('Оперативное') ? 'bg-gradient-to-br from-blue-400 to-blue-500' :
                      transcript.meeting_type.includes('Стратегическое') ? 'bg-gradient-to-br from-purple-400 to-purple-500' :
                      transcript.meeting_type.includes('Финансовое') ? 'bg-gradient-to-br from-green-400 to-green-500' :
                      transcript.meeting_type.includes('HR') ? 'bg-gradient-to-br from-pink-400 to-pink-500' :
                      transcript.meeting_type.includes('Экстренное') ? 'bg-gradient-to-br from-red-400 to-red-500' :
                      'bg-gradient-to-br from-orange-400 to-orange-500'
                    }`}>
                      <span className="text-lg">
                        {transcript.meeting_type.includes('Оперативное') ? '📊' :
                         transcript.meeting_type.includes('Стратегическое') ? '🎯' :
                         transcript.meeting_type.includes('Финансовое') ? '💰' :
                         transcript.meeting_type.includes('HR') ? '👥' :
                         transcript.meeting_type.includes('Экстренное') ? '🚨' :
                         '📋'}
                      </span>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-4 mb-2">
                        <h3 className="text-lg font-bold text-gray-900 group-hover:text-violet-600 transition-colors">
                          {transcript.title}
                        </h3>
                        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/analysis/${transcript.transcript_id}`);
                            }}
                            className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center text-white shadow-md hover:shadow-lg hover:scale-110 transition-all"
                            title="Открыть"
                          >
                            <span className="text-lg">📊</span>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmDelete(transcript.transcript_id);
                            }}
                            className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-400 to-red-500 flex items-center justify-center text-white shadow-md hover:shadow-lg hover:scale-110 transition-all"
                            title="Удалить"
                          >
                            <span className="text-lg">🗑️</span>
                          </button>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 mb-3">
                        <span className={`px-3 py-1.5 rounded-full text-xs font-semibold ${
                          transcript.meeting_type.includes('Оперативное') ? 'bg-blue-100 text-blue-700' :
                          transcript.meeting_type.includes('Стратегическое') ? 'bg-purple-100 text-purple-700' :
                          transcript.meeting_type.includes('Финансовое') ? 'bg-green-100 text-green-700' :
                          transcript.meeting_type.includes('HR') ? 'bg-pink-100 text-pink-700' :
                          transcript.meeting_type.includes('Экстренное') ? 'bg-red-100 text-red-700' :
                          'bg-orange-100 text-orange-700'
                        }`}>
                          {transcript.meeting_type}
                        </span>
                        <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 flex items-center gap-1">
                          <span>📅</span>
                          {format(new Date(transcript.created_at), 'dd.MM.yyyy HH:mm', { locale: ru })}
                        </span>
                      </div>

                      {transcript.key_points?.[0] && (
                        <p className="text-sm text-gray-600 mb-3 line-clamp-2 leading-relaxed">
                          {transcript.key_points[0]}
                        </p>
                      )}

                      <div className="flex items-center gap-4 text-sm">
                        <span className="flex items-center gap-1.5 text-gray-600 bg-gray-50 px-3 py-1.5 rounded-lg">
                          <span className="text-violet-500">🗣️</span>
                          <span className="font-medium">{transcript.speakers?.length || 0} спикеров</span>
                        </span>
                        <span className="flex items-center gap-1.5 text-gray-600 bg-gray-50 px-3 py-1.5 rounded-lg">
                          <span className="text-violet-500">⏱️</span>
                          <span className="font-medium">{(transcript.duration || 0 / 60).toFixed(1)} мин</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Delete confirmation */}
                  {confirmDelete === transcript.transcript_id && (
                    <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl">
                      <p className="text-sm text-red-800 font-medium mb-3">Удалить эту транскрипцию?</p>
                      <div className="flex gap-2">
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(transcript.transcript_id);
                          }}
                        >
                          Да, удалить
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmDelete(null);
                          }}
                        >
                          Отмена
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
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