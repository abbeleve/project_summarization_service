import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { useActiveTasks } from '@/hooks/useActiveTasks';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { getSpeakerColor } from '@/utils/speakerColors';

const RECENT_LIMIT = 9;

const STEP_LABELS: Record<string, string> = {
  noise_suppression: '🔇 Шумоподавление',
  transcription: '📝 Транскрибация',
  diarization: '🗣️ Диаризация',
  summarization: '📋 Суммаризация',
  db_save: '💾 Сохранение в БД',
  rag_index: '📚 RAG индексация',
  completed: '✅ Готово',
};

const STEP_ORDER = ['noise_suppression', 'transcription', 'diarization', 'summarization', 'db_save', 'rag_index', 'completed'];

const getTypeIcon = (mt: string | undefined | null): string => {
  if (mt?.includes('Оперативное')) return '📊';
  if (mt?.includes('Стратегическое')) return '🎯';
  if (mt?.includes('Финансовое')) return '💰';
  if (mt?.includes('HR')) return '👥';
  if (mt?.includes('Экстренное')) return '🚨';
  return '📋';
};

const getTypeBadge = (mt: string | undefined | null): string => {
  if (mt?.includes('Оперативное')) return 'Оперативное';
  if (mt?.includes('Стратегическое')) return 'Стратегическое';
  if (mt?.includes('Финансовое')) return 'Финансовое';
  if (mt?.includes('HR')) return 'HR';
  if (mt?.includes('Экстренное')) return 'Экстренное';
  return mt || 'Совещание';
};

const getTypeGradient = (mt: string | undefined | null): string => {
  if (mt?.includes('Финансовое')) return 'from-emerald-500 to-green-600';
  if (mt?.includes('HR')) return 'from-pink-500 to-rose-600';
  if (mt?.includes('Экстренное')) return 'from-red-500 to-rose-600';
  return 'from-blue-500 to-indigo-600';
};

const formatDuration = (minutes: number): string => {
  const totalSeconds = Math.round(minutes * 60);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
};

export const HomePage = () => {
  const navigate = useNavigate();
  const [isDragOver, setIsDragOver] = useState(false);
  const [freshTranscriptId, setFreshTranscriptId] = useState<string | null>(() => {
    // При монтировании читаем ID последней завершённой транскрипции из sessionStorage
    try {
      return sessionStorage.getItem('freshTranscriptId') || null;
    } catch {
      return null;
    }
  });

  // Множество ID транскрипций, которые пользователь уже открыл
  const [viewedIds, setViewedIds] = useState<Set<string>>(() => {
    try {
      const raw = sessionStorage.getItem('viewedTranscriptIds');
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch {
      return new Set();
    }
  });

  const { transcripts, isLoading, error, refetch } = useTranscripts({
    limit: RECENT_LIMIT,
    offset: 0,
  });

  const { tasks: allTasks } = useActiveTasks();
  const activeTask = allTasks.find(t => t.status === 'pending' || t.status === 'processing');
  const completedWithResult = allTasks.filter(
    t => t.status === 'completed' && t.result?.transcript_id
  );

  // Когда задача завершается — запоминаем ТОЛЬКО ПОСЛЕДНИЙ transcript_id и обновляем список
  useEffect(() => {
    if (completedWithResult.length === 0) return;

    const latest = completedWithResult.reduce((prev, curr) => {
      const prevTime = prev.updated_at ? new Date(prev.updated_at).getTime() : prev.addedAt;
      const currTime = curr.updated_at ? new Date(curr.updated_at).getTime() : curr.addedAt;
      return currTime > prevTime ? curr : prev;
    });
    const tid = latest.result!.transcript_id;

    if (tid !== freshTranscriptId) {
      // Новая транскрипция — убираем её из просмотренных, чтобы показать бадж
      setFreshTranscriptId(tid);
      sessionStorage.setItem('freshTranscriptId', tid);
      setViewedIds(prev => {
        if (!prev.has(tid)) return prev;
        const next = new Set(prev);
        next.delete(tid);
        sessionStorage.setItem('viewedTranscriptIds', JSON.stringify([...next]));
        return next;
      });
      refetch(); // перезапрашиваем список транскрипций
    }
  }, [completedWithResult, refetch]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) navigate('/new-analysis', { state: { droppedFile: file } });
  }, [navigate]);

  const items = transcripts.slice(0, RECENT_LIMIT);
  // На сколько тайлов меньше показывать из-за прогресс-тайла
  const hasProgressTile = !!activeTask;
  const regularLimit = RECENT_LIMIT - 1 - (hasProgressTile ? 1 : 0);

  // Информация для прогресс-тайла
  const currentStepIndex = activeTask?.step ? STEP_ORDER.indexOf(activeTask.step) : -1;
  const displayProgress = activeTask
    ? activeTask.progress && activeTask.progress > 0
      ? activeTask.progress
      : currentStepIndex >= 0
        ? ((currentStepIndex + 1) / STEP_ORDER.length) * 100
        : 25
    : 0;

  return (
    <div className="max-w-5xl mx-auto mt-8">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-5xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight">
          Ваши недавние совещания
        </h1>
        {!isLoading && !error && (
          <p className="mt-1 text-base text-gray-500 dark:text-gray-400">
            {items.length > 0
              ? `Показано ${Math.min(items.length, regularLimit)} из ${Math.min(transcripts.length, RECENT_LIMIT - 1)}+`
              : 'У вас пока нет транскрипций'}
          </p>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <LoadingSpinner text="Загрузка..." size={'sm'} />
        </div>
      ) : error ? (
        <ErrorMessage message="Не удалось загрузить совещания" />
      ) : items.length === 0 && !activeTask ? (
        <div className="text-center py-20">
          <div className="w-24 h-24 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-5">
            <span className="text-5xl">📝</span>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Ещё нет записей
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6 max-w-md mx-auto">
            Загрузите аудиофайл на странице «Новый анализ», чтобы получить первую транскрипцию
          </p>
          <button
            onClick={() => navigate('/new-analysis')}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold shadow-lg hover:shadow-xl hover:scale-105 transition-all"
          >
            ➜ Новый анализ
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Первый тайл — Новый анализ */}
          <button
            onClick={() => navigate('/new-analysis')}
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`group relative rounded-2xl border-2 border-dashed p-6 text-center hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 w-full flex flex-col items-center justify-center min-h-[200px] ${
              isDragOver
                ? 'bg-blue-600 border-blue-400 scale-[1.02] shadow-xl'
                : 'bg-gray-200 dark:bg-dark-base-700 border-gray-400 dark:border-dark-base-500'
            }`}
          >
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-3 group-hover:scale-110 transition-all duration-300 ${
              isDragOver ? 'bg-blue-500' : 'bg-gray-300 dark:bg-dark-base-600 group-hover:bg-gray-400 dark:group-hover:bg-dark-base-500'
            }`}>
              <span className={`text-3xl font-light ${isDragOver ? 'text-white' : 'text-gray-500 dark:text-gray-400'}`}>
                {isDragOver ? '📂' : '+'}
              </span>
            </div>
            <span className={`text-lg font-bold ${isDragOver ? 'text-white' : 'text-gray-600 dark:text-gray-300'}`}>
              {isDragOver ? 'Отпустите файл' : 'Новый анализ'}
            </span>
            <span className={`text-sm mt-1 ${isDragOver ? 'text-blue-200' : 'text-gray-500 dark:text-gray-500'}`}>
              {isDragOver ? 'Файл будет загружен' : 'Загрузить аудиофайл'}
            </span>
          </button>

          {/* Прогресс-тайл активной задачи */}
          {activeTask && (
            <div className="rounded-2xl border-2 border-blue-300 dark:border-blue-600 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 p-6 flex flex-col items-center justify-center min-h-[200px] animate-pulse">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center mb-3 shadow-lg">
                <span className="text-2xl text-white">⏳</span>
              </div>
              <span className="text-base font-bold text-blue-700 dark:text-blue-300 mb-1">
                Обработка...
              </span>
              <span className="text-sm text-blue-500 dark:text-blue-400 mb-3">
                {activeTask.step ? STEP_LABELS[activeTask.step] || activeTask.step : 'Запуск...'}
              </span>
              {/* Progress bar */}
              <div className="w-full bg-blue-200 dark:bg-blue-900/50 rounded-full h-2 mb-1">
                <div
                  className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500"
                  style={{ width: `${Math.min(displayProgress, 100)}%` }}
                />
              </div>
              <span className="text-xs text-blue-400 dark:text-blue-500 font-medium">
                {Math.round(displayProgress)}%
              </span>
            </div>
          )}

          {/* Тайлы транскрипций */}
          {items.slice(0, regularLimit).map((tr) => {
            const isFresh = tr.transcript_id === freshTranscriptId && !viewedIds.has(tr.transcript_id);
            return (
              <button
                key={tr.transcript_id}
                onClick={() => {
                  // Помечаем транскрипцию как просмотренную (убираем бадж "Только что")
                  setViewedIds(prev => {
                    if (prev.has(tr.transcript_id)) return prev;
                    const next = new Set(prev);
                    next.add(tr.transcript_id);
                    sessionStorage.setItem('viewedTranscriptIds', JSON.stringify([...next]));
                    return next;
                  });
                  navigate(`/analysis/${tr.transcript_id}`);
                }}
                className={`group relative rounded-2xl border-2 p-6 text-left hover:shadow-xl hover:-translate-y-1 transition-all duration-300 w-full flex flex-col min-h-[200px] ${
                  isFresh
                    ? 'bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-green-400 dark:border-green-600 shadow-lg shadow-green-200/50 dark:shadow-green-900/30'
                    : 'bg-white dark:bg-dark-base-800 border-gray-200 dark:border-dark-base-700 hover:border-blue-300 dark:hover:border-blue-700'
                }`}
              >
                {/* Badge "Только что" */}
                {isFresh && (
                  <div className="absolute -top-2.5 right-4 z-10 px-3 py-0.5 rounded-full bg-gradient-to-r from-green-500 to-emerald-500 text-white text-[10px] font-bold uppercase tracking-wider shadow-md">
                    ✨ Только что
                  </div>
                )}

                {/* Top accent bar */}
                <div className={`h-2 rounded-full bg-gradient-to-r ${getTypeGradient(tr.meeting_type)} mb-5 w-20 group-hover:w-full transition-all duration-500`} />

                {/* Title */}
                <h3 className="text-xl font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors line-clamp-2 mb-4 leading-snug min-h-[3rem]">
                  {tr.title}
                </h3>

                {/* Meta row */}
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-4">
                  <span>{format(new Date(tr.created_at), 'd MMM, HH:mm', { locale: ru })}</span>
                  <span className="text-gray-300 dark:text-dark-base-600">•</span>
                  <span>{formatDuration(tr.duration || 0)}</span>
                </div>

                {/* Tag */}
                <div className="mt-auto">
                  <span className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold ${
                    tr.meeting_type?.includes('Финансовое')
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                      : tr.meeting_type?.includes('HR')
                        ? 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300'
                        : tr.meeting_type?.includes('Экстренное')
                          ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                          : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  }`}>
                    <span>{getTypeIcon(tr.meeting_type)}</span>
                    <span>{getTypeBadge(tr.meeting_type)}</span>
                  </span>
                </div>

                {/* Speakers row */}
                {(tr.speakers?.length ?? 0) > 0 && (
                  <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100 dark:border-dark-base-700 text-sm text-gray-400 dark:text-gray-500">
                    <span>🗣️</span>
                    <div className="flex items-center -space-x-2">
                      {tr.speakers!.slice(0, 3).map((sp, idx) => {
                        const palette = getSpeakerColor(sp);
                        const initials = sp.replace('SPEAKER_', '').replace(/[^a-zA-Zа-яА-ЯёЁ0-9]/g, '').slice(0, 2).toUpperCase() || '?';
                        return (
                          <div
                            key={`${sp}-${idx}`}
                            className={`w-6 h-6 rounded-full ${palette.bg} ring-2 ring-white dark:ring-dark-base-800 flex items-center justify-center text-[10px] font-bold text-white shadow-sm`}
                            title={sp}
                          >
                            {initials}
                          </div>
                        );
                      })}
                    </div>
                    {(tr.speakers?.length ?? 0) > 3 && (
                      <div className="w-6 h-6 rounded-full bg-gray-200 dark:bg-dark-base-700 ring-2 ring-white dark:ring-dark-base-800 flex items-center justify-center text-[10px] font-semibold text-gray-600 dark:text-gray-300 shadow-sm">
                        +{tr.speakers!.length - 3}
                      </div>
                    )}
                    <span className="ml-1">{tr.speakers?.length || 0} спикер{(tr.speakers?.length ?? 0) > 1 ? 'а' : ''}</span>
                  </div>
                )}

                {/* Hover arrow */}
                <div className="absolute top-5 right-5 w-10 h-10 rounded-full bg-blue-500/10 dark:bg-blue-400/10 flex items-center justify-center opacity-0 group-hover:opacity-100 group-hover:scale-100 scale-75 transition-all duration-300">
                  <span className="text-blue-600 dark:text-blue-400 text-base font-bold">➜</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
