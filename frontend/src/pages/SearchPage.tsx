import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ragApi } from '@/api/rag';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import type { RAGResult, RAGSearchFilters } from '@/types/transcript';

// Common meeting types for filter dropdown
const MEETING_TYPES = [
  'Оперативное совещание',
  'Стратегическая сессия',
  'Финансовое совещание',
  'HR совещание',
  'Экстренное совещание',
  '1-on-1',
  'Daily',
  'Sprint Planning',
  'Sprint Review',
  'Ретроспектива',
  'Не определено',
];

export const SearchPage = () => {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<RAGSearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [results, setResults] = useState<RAGResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Date filter state
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [meetingType, setMeetingType] = useState('');
  const [speakerFilter, setSpeakerFilter] = useState('');

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const doSearch = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    // Build filters
    const activeFilters: RAGSearchFilters = {};
    if (dateFrom) activeFilters.date_from = dateFrom;
    if (dateTo) activeFilters.date_to = dateTo;
    if (meetingType) activeFilters.meeting_type = meetingType;
    if (speakerFilter.trim()) activeFilters.speaker = speakerFilter.trim();

    try {
      const res = await ragApi.searchContext(trimmed, undefined, 20, Object.keys(activeFilters).length > 0 ? activeFilters : undefined);
      setResults(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка при поиске';
      setError(msg);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [query, dateFrom, dateTo, meetingType, speakerFilter]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') doSearch();
  };

  const clearAll = () => {
    setQuery('');
    setResults([]);
    setHasSearched(false);
    setError(null);
    setDateFrom('');
    setDateTo('');
    setMeetingType('');
    setSpeakerFilter('');
    setFilters({});
    inputRef.current?.focus();
  };

  const formatScore = (score: number): string => {
    return (score * 100).toFixed(1);
  };

  const formatDate = (iso: string | undefined): string => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'numeric',
        year: 'numeric',
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="max-w-5xl mx-auto mt-6 px-4">
      {/* Header */}
      <h1 className="text-4xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight mb-6">
        🔍 Поиск по совещаниям
      </h1>

      {/* Search bar */}
      <div className="flex gap-3 mb-4">
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Поиск по всем вашим совещаниям..."
            className="w-full px-5 py-3.5 rounded-xl border border-gray-200 dark:border-dark-base-700
                       bg-white dark:bg-dark-base-900 text-gray-900 dark:text-white
                       placeholder-gray-400 dark:placeholder-gray-500
                       text-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       transition-all"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); inputRef.current?.focus(); }}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl"
            >
              ×
            </button>
          )}
        </div>
        <button
          onClick={doSearch}
          disabled={!query.trim() || isSearching}
          className="px-8 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400
                     disabled:cursor-not-allowed text-white font-semibold text-lg shadow-sm
                     transition-colors"
        >
          {isSearching ? 'Поиск...' : 'Найти'}
        </button>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`px-4 py-3.5 rounded-xl border font-medium transition-colors text-sm
                     ${showFilters
                       ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
                       : 'border-gray-200 dark:border-dark-base-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-base-800'
                     }`}
        >
          ⚙ Фильтры
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="mb-6 p-5 rounded-xl border border-gray-200 dark:border-dark-base-700
                        bg-gray-50 dark:bg-dark-base-800/50">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Date from */}
            <div>
              <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                Дата с
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-dark-base-700
                           bg-white dark:bg-dark-base-900 text-gray-900 dark:text-white text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Date to */}
            <div>
              <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                Дата по
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-dark-base-700
                           bg-white dark:bg-dark-base-900 text-gray-900 dark:text-white text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Meeting type */}
            <div>
              <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                Тип встречи
              </label>
              <select
                value={meetingType}
                onChange={(e) => setMeetingType(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-dark-base-700
                           bg-white dark:bg-dark-base-900 text-gray-900 dark:text-white text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Все</option>
                {MEETING_TYPES.map((mt) => (
                  <option key={mt} value={mt}>{mt}</option>
                ))}
              </select>
            </div>

            {/* Speaker */}
            <div>
              <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1.5">
                Участник
              </label>
              <input
                type="text"
                value={speakerFilter}
                onChange={(e) => setSpeakerFilter(e.target.value)}
                placeholder="Имя или SPEAKER_XX"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-dark-base-700
                           bg-white dark:bg-dark-base-900 text-gray-900 dark:text-white text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
      )}

      {/* Active filters indicator */}
      {(dateFrom || dateTo || meetingType || speakerFilter) && (
        <div className="mb-4 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span>Активные фильтры:</span>
          {dateFrom && <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">с {dateFrom}</span>}
          {dateTo && <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">по {dateTo}</span>}
          {meetingType && <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">{meetingType}</span>}
          {speakerFilter && <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">{speakerFilter}</span>}
          <button onClick={clearAll} className="ml-2 text-red-500 hover:text-red-700 text-xs underline">
            Сбросить всё
          </button>
        </div>
      )}

      {/* Error state */}
      {error && <ErrorMessage message={error} />}

      {/* Loading */}
      {isSearching && (
        <div className="flex justify-center py-20">
          <LoadingSpinner text="Поиск..." size="sm" />
        </div>
      )}

      {/* No results */}
      {!isSearching && hasSearched && results.length === 0 && !error && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4">🔍</div>
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            Ничего не найдено по запросу «{query}»
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            Попробуйте изменить запрос или убрать фильтры
          </p>
        </div>
      )}

      {/* Results */}
      {!isSearching && results.length > 0 && (
        <>
          <div className="mb-3 text-sm text-gray-500 dark:text-gray-400">
            Найдено {results.length} результатов
          </div>

          <div className="flex flex-col gap-3">
            {results.map((result, idx) => {
              const p = result.payload;
              return (
                <div
                  key={`${p.transcript_id}-${idx}`}
                  onClick={() => navigate(`/analysis/${p.transcript_id}`)}
                  className="p-5 rounded-xl border border-gray-200 dark:border-dark-base-700
                             bg-white dark:bg-dark-base-900 cursor-pointer
                             hover:shadow-md hover:border-blue-300 dark:hover:border-blue-700
                             transition-all"
                >
                  <div className="flex items-start justify-between gap-4 mb-2">
                    {/* Title + metadata */}
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                        {p.title || 'Без названия'}
                      </h3>
                      <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {p.meeting_type && (
                          <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-dark-base-800">
                            {p.meeting_type}
                          </span>
                        )}
                        {formatDate(p.created_at) && (
                          <span>📅 {formatDate(p.created_at)}</span>
                        )}
                        {p.speaker && (
                          <span>🎤 {p.speaker}</span>
                        )}
                        <span className="text-blue-500 font-medium">
                          {formatScore(result.score)}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Text fragment */}
                  <p className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed line-clamp-3">
                    {p.text}
                  </p>

                  {/* Time indicator */}
                  {p.start_time > 0 && (
                    <div className="mt-2 text-xs text-gray-400 dark:text-gray-500">
                      ⏱ {Math.floor(p.start_time / 60)}:{String(Math.floor(p.start_time % 60)).padStart(2, '0')}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Initial state */}
      {!hasSearched && !isSearching && (
        <div className="text-center py-24">
          <div className="text-6xl mb-4">🔍</div>
          <p className="text-gray-400 dark:text-gray-500 text-lg">
            Введите поисковый запрос, чтобы найти информацию в ваших совещаниях
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            Поиск работает по всему тексту транскрипций, суммаризациям и ключевым точкам
          </p>
        </div>
      )}
    </div>
  );
};
