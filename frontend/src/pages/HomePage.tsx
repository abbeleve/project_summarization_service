import { useState, useCallback, useEffect, useRef } from 'react';
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
  const [searchQuery, setSearchQuery] = useState('');
  const [actualSearchQuery, setActualSearchQuery] = useState(''); // Для поиска по кнопке
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actualStartDate, setActualStartDate] = useState('');
  const [actualEndDate, setActualEndDate] = useState('');

  const { transcripts, isLoading, error, total, refetch, processAudio, deleteTranscript } = useTranscripts({
    limit: TRANSCRIPTS_PER_PAGE,
    offset,
    searchQuery: actualSearchQuery || undefined,
    startDate: actualStartDate || undefined,
    endDate: actualEndDate || undefined
  });
  const { tasks, addTask, removeTask } = useActiveTasks();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);

  // Конвертирует дд/мм/гггг в ISO YYYY-MM-DD
  const toISODate = (val: string): string => {
    const match = val.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (match) return `${match[3]}-${match[2]}-${match[1]}`;
    return val;
  };

  // Конвертирует ISO YYYY-MM-DD в дд/мм/гггг
  const toDisplayDate = (val: string): string => {
    const match = val.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (match) return `${match[3]}/${match[2]}/${match[1]}`;
    return val;
  };

  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);

  const applyFilters = () => {
    setActualSearchQuery(searchQuery);
    setActualStartDate(toISODate(startDate));
    setActualEndDate(toISODate(endDate));
    setOffset(0);
  };

  // Проверяем завершённые задачи и показываем уведомление
  useEffect(() => {
    const completedTask = tasks.find(t => t.status === 'completed' && t.result?.transcript_id);
    if (completedTask) {
      setTaskError(null);
      refetch();
      // Удаляем задачу из списка после обновления
      removeTask(completedTask.task_id);
    }
  }, [tasks.map(t => `${t.task_id}-${t.status}`).join(',')]); // Только при изменении статуса задач

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

  const startEditing = (id: string, currentTitle: string) => {
    setEditingId(id);
    setEditTitle(currentTitle);
  };

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) return;
    
    setSavingId(id);
    try {
      await transcriptsApi.rename(id, editTitle.trim());
      await refetch();
      setEditingId(null);
    } catch (err) {
      console.error('Rename error:', err);
    } finally {
      setSavingId(null);
    }
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditTitle('');
  };

  return (
    <div className="space-y-8">
      {/* Upload section */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">📤 Новый анализ</h2>
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
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center shadow-lg">
            <span className="text-2xl">📋</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">История транскрипций</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {total > 0 ? `Всего ${total} транскрипций` : 'Пока пусто'}
            </p>
          </div>
        </div>

        {/* GPT-стиль поиск под заголовком */}
        <div className="mb-4">
          <div className="relative w-full">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') applyFilters();
              }}
              placeholder="Поиск по названию транскрипции..."
              className="w-full px-5 py-3.5 pl-12 pr-12 rounded-2xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm text-base"
            />
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 text-lg">
              🔍
            </span>
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setActualSearchQuery('');
                  setOffset(0);
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-lg transition-colors"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Фильтр по дате в формате дд/мм/гггг */}
        <div className="flex items-center gap-2 mb-6 flex-wrap">
          <div className="relative">
            <input
              type="text"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              placeholder="дд/мм/гггг"
              className="w-36 px-3 py-2 pr-9 rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-sm"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none text-sm">
              📅
            </span>
            <input
              ref={startDateRef}
              type="date"
              onChange={(e) => {
                if (e.target.value) {
                  setStartDate(toDisplayDate(e.target.value));
                }
              }}
              className="absolute right-1 top-1/2 -translate-y-1/2 w-8 h-8 opacity-0 cursor-pointer"
            />
          </div>
          <span className="text-gray-400 dark:text-gray-500 font-medium">—</span>
          <div className="relative">
            <input
              type="text"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              placeholder="дд/мм/гггг"
              className="w-36 px-3 py-2 pr-9 rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-sm"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none text-sm">
              📅
            </span>
            <input
              ref={endDateRef}
              type="date"
              onChange={(e) => {
                if (e.target.value) {
                  setEndDate(toDisplayDate(e.target.value));
                }
              }}
              className="absolute right-1 top-1/2 -translate-y-1/2 w-8 h-8 opacity-0 cursor-pointer"
            />
          </div>
          <Button
            onClick={applyFilters}
            size="sm"
            className="whitespace-nowrap"
          >
            Применить
          </Button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner text="Загрузка истории..." size={'sm'} />
          </div>
        ) : error ? (
          <ErrorMessage message="Не удалось загрузить историю" />
        ) : !transcripts?.length ? (
          <Card className="p-12 text-center dark:bg-dark-base-800 dark:border-dark-base-700">
            <div className="max-w-md mx-auto">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-100 to-blue-100 dark:from-blue-900/30 dark:to-blue-900/30 flex items-center justify-center mx-auto mb-4">
                <span className="text-4xl">📝</span>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">У вас пока нет транскрипций</h3>
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                Загрузите аудиофайл выше, чтобы начать анализ встречи
              </p>
            </div>
          </Card>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {searchQuery ? (
                  <>
                    Найдено <span className="font-semibold text-gray-900 dark:text-white">{transcripts.length}</span> из <span className="font-semibold text-gray-900 dark:text-white">{total}</span> транскрипций по запросу "<span className="font-medium text-blue-600 dark:text-blue-400">{searchQuery}</span>"
                  </>
                ) : (
                  <>
                    Показано <span className="font-semibold text-gray-900 dark:text-white">{transcripts.length}</span> из <span className="font-semibold text-gray-900 dark:text-white">{total}</span> транскрипций
                  </>
                )}
              </p>
            </div>
            <div className="grid gap-4">
              {transcripts.map((transcript) => (
                <div
                  key={transcript.transcript_id}
                  className="group bg-white dark:bg-dark-base-800 rounded-2xl border border-gray-200 dark:border-dark-base-700 p-5 hover:shadow-xl hover:border-blue-200 dark:hover:border-blue-800 transition-all duration-300 cursor-pointer"
                  onClick={() => navigate(`/analysis/${transcript.transcript_id}`)}
                >
                  <div className="flex items-start gap-4">
                    {/* Иконка типа встречи */}
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm ${
                      transcript.meeting_type?.includes('Оперативное') ? 'bg-gradient-to-br from-blue-400 to-blue-500' :
                      transcript.meeting_type?.includes('Стратегическое') ? 'bg-gradient-to-br from-blue-400 to-blue-500' :
                      transcript.meeting_type?.includes('Финансовое') ? 'bg-gradient-to-br from-green-400 to-green-500' :
                      transcript.meeting_type?.includes('HR') ? 'bg-gradient-to-br from-pink-400 to-pink-500' :
                      transcript.meeting_type?.includes('Экстренное') ? 'bg-gradient-to-br from-red-400 to-red-500' :
                      'bg-gradient-to-br from-orange-400 to-orange-500'
                    }`}>
                      <span className="text-lg">
                        {transcript.meeting_type?.includes('Оперативное') ? '📊' :
                         transcript.meeting_type?.includes('Стратегическое') ? '🎯' :
                         transcript.meeting_type?.includes('Финансовое') ? '💰' :
                         transcript.meeting_type?.includes('HR') ? '👥' :
                         transcript.meeting_type?.includes('Экстренное') ? '🚨' :
                         '📋'}
                      </span>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-4 mb-2">
                        {editingId === transcript.transcript_id ? (
                          <div className="flex-1 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleRename(transcript.transcript_id);
                                if (e.key === 'Escape') cancelEditing();
                              }}
                              className="flex-1 px-3 py-1.5 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                              placeholder="Новое название"
                              autoFocus
                            />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRename(transcript.transcript_id);
                              }}
                              className="w-8 h-8 rounded-lg bg-green-500 hover:bg-green-600 text-white flex items-center justify-center transition-colors"
                              title="Сохранить"
                            >
                              {savingId === transcript.transcript_id ? '...' : '💾'}
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                cancelEditing();
                              }}
                              className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-dark-base-700 hover:bg-gray-300 dark:hover:bg-dark-base-600 text-gray-700 dark:text-gray-300 flex items-center justify-center transition-colors"
                              title="Отмена"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <>
                            <h3 className="text-lg font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                              {transcript.title}
                            </h3>
                            <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate(`/analysis/${transcript.transcript_id}`);
                                }}
                                className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center text-white shadow-md hover:shadow-lg hover:scale-110 transition-all"
                                title="Открыть"
                              >
                                <span className="text-lg">📊</span>
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startEditing(transcript.transcript_id, transcript.title);
                                }}
                                className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center text-white shadow-md hover:shadow-lg hover:scale-110 transition-all"
                                title="Переименовать"
                              >
                                <span className="text-lg">✏️</span>
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
                          </>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-2 mb-3">
                        <span className={`px-3 py-1.5 rounded-full text-xs font-semibold ${
                          transcript.meeting_type?.includes('Оперативное') ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                          transcript.meeting_type?.includes('Стратегическое') ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                          transcript.meeting_type?.includes('Финансовое') ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                          transcript.meeting_type?.includes('HR') ? 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300' :
                          transcript.meeting_type?.includes('Экстренное') ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                          'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
                        }`}>
                          {transcript.meeting_type || 'Не определено'}
                        </span>
                        <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-dark-base-700 dark:text-gray-300 flex items-center gap-1">
                          <span>📅</span>
                          {format(new Date(transcript.created_at), 'dd.MM.yyyy HH:mm', { locale: ru })}
                        </span>
                      </div>

                      {transcript.key_points?.[0] && (
                        <p className="text-sm text-gray-600 dark:text-gray-300 mb-3 line-clamp-2 leading-relaxed">
                          {transcript.key_points[0]}
                        </p>
                      )}

                      <div className="flex items-center gap-4 text-sm">
                        <span className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-dark-base-700 px-3 py-1.5 rounded-lg">
                          <span className="text-blue-500">🗣️</span>
                          <span className="font-medium">{transcript.speakers?.length || 0} спикеров</span>
                        </span>
                        <span className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-dark-base-700 px-3 py-1.5 rounded-lg">
                          <span className="text-blue-500">⏱️</span>
                          <span className="font-medium">{(transcript.duration || 0).toFixed(1)} мин</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Delete confirmation */}
                  {confirmDelete === transcript.transcript_id && (
                    <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
                      <p className="text-sm text-red-800 dark:text-red-300 font-medium mb-3">Удалить эту транскрипцию?</p>
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