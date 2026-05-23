import { useNavigate } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const RECENT_LIMIT = 9;

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

  const { transcripts, isLoading, error } = useTranscripts({
    limit: RECENT_LIMIT,
    offset: 0,
  });

  // Берем максимум 9
  const items = transcripts.slice(0, RECENT_LIMIT);

  return (
    <div className="max-w-5xl mx-auto mt-8">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight">
          Ваши недавние совещания
        </h1>
        {!isLoading && !error && (
          <p className="mt-1 text-base text-gray-500 dark:text-gray-400">
            {items.length > 0
              ? `Показано ${Math.min(items.length, RECENT_LIMIT - 1)} из ${transcripts.length >= RECENT_LIMIT ? `${transcripts.length}+` : transcripts.length}`
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
      ) : items.length === 0 ? (
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
            className="group relative bg-gray-900 dark:bg-dark-base-700 rounded-2xl border-2 border-dashed border-gray-400 dark:border-dark-base-500 p-6 text-center hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 w-full flex flex-col items-center justify-center min-h-[200px]"
          >
            <div className="w-14 h-14 rounded-2xl bg-gray-700 dark:bg-dark-base-600 flex items-center justify-center mb-3 group-hover:bg-gray-600 dark:group-hover:bg-dark-base-500 group-hover:scale-110 transition-all duration-300">
              <span className="text-3xl text-gray-300 dark:text-gray-400 font-light">+</span>
            </div>
            <span className="text-lg font-bold text-gray-200 dark:text-gray-300">Новый анализ</span>
            <span className="text-sm text-gray-400 dark:text-gray-500 mt-1">Загрузить аудиофайл</span>
          </button>

          {items.slice(0, RECENT_LIMIT - 1).map((tr) => (
            <button
              key={tr.transcript_id}
              onClick={() => navigate(`/analysis/${tr.transcript_id}`)}
              className="group relative bg-white dark:bg-dark-base-800 rounded-2xl border border-gray-200 dark:border-dark-base-700 p-6 text-left hover:shadow-xl hover:border-blue-300 dark:hover:border-blue-700 hover:-translate-y-1 transition-all duration-300 w-full flex flex-col min-h-[200px]"
            >
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
                <div className="flex items-center gap-1.5 mt-4 pt-4 border-t border-gray-100 dark:border-dark-base-700 text-sm text-gray-400 dark:text-gray-500">
                  <span>🗣️</span>
                  <span>{tr.speakers?.length || 0} спикер{(tr.speakers?.length ?? 0) > 1 ? 'а' : ''}</span>
                </div>
              )}

              {/* Hover arrow */}
              <div className="absolute top-5 right-5 w-10 h-10 rounded-full bg-blue-500/10 dark:bg-blue-400/10 flex items-center justify-center opacity-0 group-hover:opacity-100 group-hover:scale-100 scale-75 transition-all duration-300">
                <span className="text-blue-600 dark:text-blue-400 text-base font-bold">➜</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
