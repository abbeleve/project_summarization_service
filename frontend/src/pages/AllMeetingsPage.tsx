import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useTranscripts } from '@/hooks/useTranscripts';
import { transcriptsApi } from '@/api/transcripts';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { TranscriptTableView, type TranscriptRow } from '@/components/transcriptions/TranscriptTableView';

const PAGE_SIZE = 50;

const toISODate = (val: string): string => {
  const m = val.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : val;
};
const toDisplayDate = (val: string): string => {
  const m = val.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : val;
};

export const AllMeetingsPage = () => {
  const [offset, setOffset] = useState(0);
  const [allTranscripts, setAllTranscripts] = useState<TranscriptRow[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actualStartDate, setActualStartDate] = useState('');
  const [actualEndDate, setActualEndDate] = useState('');

  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);

  const resetPagination = useCallback(() => {
    setOffset(0);
    setAllTranscripts([]);
  }, []);

  const { transcripts, isLoading, error, total, refetch } = useTranscripts({
    limit: PAGE_SIZE,
    offset,
    startDate: actualStartDate || undefined,
    endDate: actualEndDate || undefined,
  });

  const hasMore = allTranscripts.length < total;

  useEffect(() => {
    if (isLoading || transcripts.length === 0) return;
    const mapped: TranscriptRow[] = transcripts.map(t => ({
      transcript_id: t.transcript_id,
      title: t.title,
      created_at: t.created_at,
      meeting_type: t.meeting_type,
      duration: t.duration,
      speakers: t.speakers,
      summary: t.summary,
      key_points: t.key_points as string[] | null,
    }));
    if (offset === 0) {
      setAllTranscripts(mapped);
    } else {
      setAllTranscripts(prev => {
        const ids = new Set(prev.map(t => t.transcript_id));
        const newOnes = mapped.filter(t => !ids.has(t.transcript_id));
        return newOnes.length ? [...prev, ...newOnes] : prev;
      });
    }
  }, [transcripts, isLoading, offset]);

  const loadMore = useCallback(() => {
    if (!isLoading && hasMore) setOffset(prev => prev + PAGE_SIZE);
  }, [isLoading, hasMore]);

  const applyFilters = useCallback(() => {
    setActualStartDate(toISODate(startDate));
    const isoEnd = toISODate(endDate);
    setActualEndDate(isoEnd ? `${isoEnd}T23:59:59` : '');
    resetPagination();
  }, [startDate, endDate, resetPagination]);

  const clearFilters = useCallback(() => {
    setSearchQuery('');
    setFilterType('all');
    setStartDate('');
    setEndDate('');
    setActualStartDate('');
    setActualEndDate('');
    resetPagination();
  }, [resetPagination]);

  const handleDelete = useCallback(async (id: string) => {
    await transcriptsApi.delete(id);
    setAllTranscripts(prev => prev.filter(t => t.transcript_id !== id));
    refetch();
  }, [refetch]);

  const handleRename = useCallback(async (id: string, title: string) => {
    await transcriptsApi.rename(id, title);
    setAllTranscripts(prev => prev.map(t => t.transcript_id === id ? { ...t, title } : t));
    refetch();
  }, [refetch]);

  // Client-side search + type filter
  const filtered: TranscriptRow[] = useMemo(() => {
    let items = [...allTranscripts];
    if (actualStartDate) {
      const start = new Date(actualStartDate).getTime();
      items = items.filter(t => new Date(t.created_at).getTime() >= start);
    }
    if (actualEndDate) {
      const end = new Date(actualEndDate).getTime();
      items = items.filter(t => new Date(t.created_at).getTime() <= end);
    }
    if (filterType !== 'all') {
      items = items.filter(t => t.meeting_type?.includes(filterType));
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      items = items.filter(t =>
        t.title.toLowerCase().includes(q) ||
        t.meeting_type?.toLowerCase().includes(q) ||
        t.summary?.toLowerCase().includes(q)
      );
    }
    return items;
  }, [allTranscripts, filterType, searchQuery, actualStartDate, actualEndDate]);

  const hasFilters = actualStartDate || actualEndDate || searchQuery || filterType !== 'all';
  const isFirstLoad = isLoading && allTranscripts.length === 0 && offset === 0;

  return (
    <div className="max-w-7xl mx-auto mt-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight">
          Ваши совещания
        </h1>
        <p className="mt-1 text-base text-gray-500 dark:text-gray-400">
          {total > 0
            ? `Всего ${total} ${total === 1 ? 'совещание' : total < 5 ? 'совещания' : 'совещаний'}`
            : 'Загрузка...'}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-start gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
            placeholder="Поиск по названию, типу, содержанию..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
          {searchQuery && (
            <button onClick={() => { setSearchQuery(''); resetPagination(); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer text-xs">✕</button>
          )}
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none">🔍</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Дата:</span>
          <div className="relative">
            <input type="text" value={startDate} onChange={(e) => setStartDate(e.target.value)}
              placeholder="дд/мм/гггг"
              className="w-28 pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <button type="button" onClick={() => startDateRef.current?.showPicker()}
              className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2"/><line x1="3" y1="10" x2="21" y2="10" strokeWidth="2"/><line x1="8" y1="2" x2="8" y2="6" strokeWidth="2"/><line x1="16" y1="2" x2="16" y2="6" strokeWidth="2"/></svg>
            </button>
            <input ref={startDateRef} type="date" onChange={(e) => { if (e.target.value) setStartDate(toDisplayDate(e.target.value)); }} className="sr-only" />
          </div>
          <span className="text-gray-400 dark:text-gray-500 text-xs">—</span>
          <div className="relative">
            <input type="text" value={endDate} onChange={(e) => setEndDate(e.target.value)}
              placeholder="дд/мм/гггг"
              className="w-28 pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <button type="button" onClick={() => endDateRef.current?.showPicker()}
              className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2"/><line x1="3" y1="10" x2="21" y2="10" strokeWidth="2"/><line x1="8" y1="2" x2="8" y2="6" strokeWidth="2"/><line x1="16" y1="2" x2="16" y2="6" strokeWidth="2"/></svg>
            </button>
            <input ref={endDateRef} type="date" onChange={(e) => { if (e.target.value) setEndDate(toDisplayDate(e.target.value)); }} className="sr-only" />
          </div>
          <button onClick={applyFilters}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-blue-500 hover:bg-blue-600 text-white transition-colors cursor-pointer">OK</button>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Тип:</span>
          {['all', 'Оперативное', 'Стратегическое', 'Финансовое', 'HR', 'Экстренное'].map(type => (
            <button key={type} onClick={() => { setFilterType(type); resetPagination(); }}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer ${
                filterType === type
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 dark:bg-dark-base-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-dark-base-700'
              }`}
            >{type === 'all' ? 'Все' : type}</button>
          ))}
        </div>

        {hasFilters && (
          <button onClick={clearFilters}
            className="px-3 py-1.5 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
          >✕ Сбросить все</button>
        )}
      </div>

      {/* Content */}
      {isFirstLoad ? (
        <div className="flex justify-center py-20">
          <LoadingSpinner text="Загрузка совещаний..." size="sm" />
        </div>
      ) : error ? (
        <ErrorMessage message="Не удалось загрузить совещания" />
      ) : (
        <TranscriptTableView
          transcripts={filtered}
          total={total}
          isLoading={isLoading}
          hasFilters={hasFilters}
          onDelete={handleDelete}
          onRename={handleRename}
          onLoadMore={loadMore}
          onRefresh={clearFilters}
          emptyMessage={hasFilters ? 'Ничего не найдено' : 'Ещё нет совещаний'}
          emptyHint={hasFilters ? 'Попробуйте изменить параметры поиска или сбросить фильтры' : 'Загрузите аудиофайл на странице «Новый анализ»'}
        />
      )}
    </div>
  );
};
