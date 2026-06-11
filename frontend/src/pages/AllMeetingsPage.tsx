import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { transcriptsApi } from '@/api/transcripts';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const PAGE_SIZE = 50;

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

type SortField = 'date' | 'title' | 'type' | 'duration' | 'speakers';
type SortDir = 'asc' | 'desc';

export const AllMeetingsPage = () => {
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [allTranscripts, setAllTranscripts] = useState<Array<{
    transcript_id: string;
    title: string;
    created_at: string;
    meeting_type: string;
    duration?: number;
    speakers?: string[];
    summary?: string | null;
    key_points?: string[] | null;
  }>>([]);

  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actualStartDate, setActualStartDate] = useState('');
  const [actualEndDate, setActualEndDate] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);

  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);

  const toISODate = (val: string): string => {
    const m = val.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    return val;
  };
  const toDisplayDate = (val: string): string => {
    const m = val.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    return val;
  };

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

  // Accumulate transcripts
  useEffect(() => {
    if (isLoading || transcripts.length === 0) return;
    if (offset === 0) {
      setAllTranscripts(transcripts.map(t => ({
        transcript_id: t.transcript_id,
        title: t.title,
        created_at: t.created_at,
        meeting_type: t.meeting_type,
        duration: t.duration,
        speakers: t.speakers,
        summary: t.summary,
        key_points: t.key_points,
      })));
    } else {
      setAllTranscripts(prev => {
        const existingIds = new Set(prev.map(t => t.transcript_id));
        const newOnes = transcripts
          .filter(t => !existingIds.has(t.transcript_id))
          .map(t => ({
            transcript_id: t.transcript_id,
            title: t.title,
            created_at: t.created_at,
            meeting_type: t.meeting_type,
            duration: t.duration,
            speakers: t.speakers,
            summary: t.summary,
            key_points: t.key_points,
          }));
        if (newOnes.length === 0) return prev;
        return [...prev, ...newOnes];
      });
    }
  }, [transcripts, isLoading, offset]);

  const loadMore = useCallback(() => {
    if (!isLoading && hasMore) {
      setOffset(prev => prev + PAGE_SIZE);
    }
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
    try {
      await transcriptsApi.delete(id);
      setDeletingId(null);
      setAllTranscripts(prev => prev.filter(t => t.transcript_id !== id));
      refetch();
    } catch (err) {
      console.error('Delete error:', err);
    }
  }, [refetch]);

  const handleRename = useCallback(async (id: string) => {
    if (!editTitle.trim()) return;
    setSavingId(id);
    try {
      const res = await transcriptsApi.rename(id, editTitle.trim());
      setAllTranscripts(prev =>
        prev.map(t => t.transcript_id === id ? { ...t, title: res.title } : t)
      );
      setEditingId(null);
      refetch();
    } catch (err) {
      console.error('Rename error:', err);
    } finally {
      setSavingId(null);
    }
  }, [editTitle, refetch]);

  const hasFilters = actualStartDate || actualEndDate || searchQuery || filterType !== 'all';

  // Filtering & sorting
  const filtered = useMemo(() => {
    let items = [...allTranscripts];

    // Date filter (client-side for already loaded data)
    if (actualStartDate) {
      const start = new Date(actualStartDate).getTime();
      items = items.filter(t => new Date(t.created_at).getTime() >= start);
    }
    if (actualEndDate) {
      const end = new Date(actualEndDate).getTime();
      items = items.filter(t => new Date(t.created_at).getTime() <= end);
    }

    // Type filter
    if (filterType !== 'all') {
      items = items.filter(t => t.meeting_type?.includes(filterType));
    }

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      items = items.filter(t =>
        t.title.toLowerCase().includes(q) ||
        t.meeting_type?.toLowerCase().includes(q) ||
        t.summary?.toLowerCase().includes(q)
      );
    }

    // Sort
    items.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'date':
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case 'title':
          cmp = a.title.localeCompare(b.title);
          break;
        case 'type':
          cmp = (a.meeting_type || '').localeCompare(b.meeting_type || '');
          break;
        case 'duration':
          cmp = (a.duration || 0) - (b.duration || 0);
          break;
        case 'speakers':
          cmp = (a.speakers?.length || 0) - (b.speakers?.length || 0);
          break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });

    return items;
  }, [allTranscripts, filterType, searchQuery, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const SortArrow = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="text-gray-300 dark:text-dark-base-600 ml-1">↕</span>;
    return <span className="text-blue-500 ml-1">{sortDir === 'desc' ? '↓' : '↑'}</span>;
  };

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

      {/* Filters bar */}
      <div className="flex flex-wrap items-start gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
            placeholder="Поиск по названию, типу, содержанию..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => { setSearchQuery(''); setActualStartDate(''); setActualEndDate(''); resetPagination(); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer text-xs"
              type="button"
            >
              ✕
            </button>
          )}
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none">🔍</span>
        </div>

        {/* Date range */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Дата:</span>
          <div className="relative">
            <input
              type="text"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              placeholder="дд/мм/гггг"
              className="w-28 pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <button
              type="button"
              onClick={() => startDateRef.current?.showPicker()}
              className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2"/><line x1="3" y1="10" x2="21" y2="10" strokeWidth="2"/><line x1="8" y1="2" x2="8" y2="6" strokeWidth="2"/><line x1="16" y1="2" x2="16" y2="6" strokeWidth="2"/></svg>
            </button>
            <input
              ref={startDateRef}
              type="date"
              onChange={(e) => { if (e.target.value) setStartDate(toDisplayDate(e.target.value)); }}
              className="sr-only"
            />
          </div>
          <span className="text-gray-400 dark:text-gray-500 text-xs">—</span>
          <div className="relative">
            <input
              type="text"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              placeholder="дд/мм/гггг"
              className="w-28 pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <button
              type="button"
              onClick={() => endDateRef.current?.showPicker()}
              className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2"/><line x1="3" y1="10" x2="21" y2="10" strokeWidth="2"/><line x1="8" y1="2" x2="8" y2="6" strokeWidth="2"/><line x1="16" y1="2" x2="16" y2="6" strokeWidth="2"/></svg>
            </button>
            <input
              ref={endDateRef}
              type="date"
              onChange={(e) => { if (e.target.value) setEndDate(toDisplayDate(e.target.value)); }}
              className="sr-only"
            />
          </div>
          <button
            onClick={applyFilters}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-blue-500 hover:bg-blue-600 text-white transition-colors cursor-pointer"
            type="button"
          >
            OK
          </button>
        </div>

        {/* Type filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Тип:</span>
          {['all', 'Оперативное', 'Стратегическое', 'Финансовое', 'HR', 'Экстренное'].map(type => (
            <button
              key={type}
              onClick={() => { setFilterType(type); resetPagination(); }}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filterType === type
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 dark:bg-dark-base-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-dark-base-700'
              }`}
            >
              {type === 'all' ? 'Все' : type}
            </button>
          ))}
        </div>

        {/* Clear all filters */}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="px-3 py-1.5 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
            type="button"
          >
            ✕ Сбросить все
          </button>
        )}
      </div>

      {/* Content */}
      {isFirstLoad ? (
        <div className="flex justify-center py-20">
          <LoadingSpinner text="Загрузка совещаний..." size="sm" />
        </div>
      ) : error ? (
        <ErrorMessage message="Не удалось загрузить совещания" />
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-20 h-20 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-4">
            <span className="text-4xl">📋</span>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            {hasFilters ? 'Ничего не найдено' : 'Ещё нет совещаний'}
          </h2>
          <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            {hasFilters
              ? 'Попробуйте изменить параметры поиска или сбросить фильтры'
              : 'Загрузите аудиофайл на странице «Новый анализ», чтобы получить первую транскрипцию'}
          </p>
        </div>
      ) : (
        <>
          {/* Table */}
          <div className="bg-white dark:bg-dark-base-900 rounded-2xl border border-gray-200 dark:border-dark-base-700 overflow-hidden shadow-sm">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_120px_90px_80px_45px_45px] gap-3 px-6 py-3 bg-gray-50 dark:bg-dark-base-800 border-b border-gray-200 dark:border-dark-base-700 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <button onClick={() => toggleSort('title')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                Название <SortArrow field="title" />
              </button>
              <button onClick={() => toggleSort('date')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                Дата <SortArrow field="date" />
              </button>
              <button onClick={() => toggleSort('type')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                Тип <SortArrow field="type" />
              </button>
              <button onClick={() => toggleSort('duration')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                Длит. <SortArrow field="duration" />
              </button>
              <button onClick={() => toggleSort('speakers')} className="flex items-center justify-center hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                <SortArrow field="speakers" />
                🗣
              </button>
              <span className="text-center"></span>
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100 dark:divide-dark-base-800">
              {filtered.map((t) => {
                const isDeleting = deletingId === t.transcript_id;
                return (
                <div
                  key={t.transcript_id}
                  className="relative grid grid-cols-[1fr_120px_90px_80px_45px_45px] gap-3 px-6 py-4 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors group"
                >
                  {isDeleting && (
                    <div
                      className="absolute inset-0 bg-red-50/90 dark:bg-red-900/25 z-10 flex items-center justify-center rounded-lg"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex gap-2">
                        <Button variant="danger" size="sm" onClick={(e) => { e.stopPropagation(); handleDelete(t.transcript_id); }}>Удалить</Button>
                        <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); setDeletingId(null); }}>Отмена</Button>
                      </div>
                    </div>
                  )}

                  {/* Title + summary */}
                  <button
                    onClick={() => { if (editingId !== t.transcript_id) navigate(`/analysis/${t.transcript_id}`); }}
                    className="min-w-0 text-left"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{getTypeIcon(t.meeting_type)}</span>
                      {editingId === t.transcript_id ? (
                        <div className="flex items-center gap-1 flex-1" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleRename(t.transcript_id);
                              if (e.key === 'Escape') setEditingId(null);
                            }}
                            className="flex-1 min-w-0 px-1.5 py-0.5 text-sm border border-gray-300 dark:border-dark-base-600 rounded bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                            autoFocus
                          />
                          <button onClick={(e) => { e.stopPropagation(); handleRename(t.transcript_id); }} className="w-6 h-6 rounded bg-green-500 hover:bg-green-600 text-white flex items-center justify-center flex-shrink-0 transition-colors text-[10px]" title="Сохранить" type="button">{savingId === t.transcript_id ? '…' : '✓'}</button>
                          <button onClick={(e) => { e.stopPropagation(); setEditingId(null); }} className="w-6 h-6 rounded bg-gray-200 dark:bg-dark-base-700 hover:bg-gray-300 dark:hover:bg-dark-base-600 text-gray-700 dark:text-gray-300 flex items-center justify-center flex-shrink-0 transition-colors text-[10px]" title="Отмена" type="button">✕</button>
                        </div>
                      ) : (
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                          {t.title}
                        </h3>
                      )}
                    </div>
                    {t.summary && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2 leading-relaxed">
                        {t.summary}
                      </p>
                    )}
                    {t.key_points && t.key_points.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {t.key_points.slice(0, 3).map((kp, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center px-2 py-0.5 rounded-md bg-gray-100 dark:bg-dark-base-800 text-[10px] text-gray-600 dark:text-gray-400 font-medium"
                          >
                            {kp.length > 40 ? kp.slice(0, 40) + '...' : kp}
                          </span>
                        ))}
                        {t.key_points.length > 3 && (
                          <span className="text-[10px] text-gray-400 dark:text-gray-500">
                            +{t.key_points.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </button>

                  {/* Date */}
                  <div className="flex flex-col justify-center">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {format(new Date(t.created_at), 'd MMM yyyy', { locale: ru })}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {format(new Date(t.created_at), 'HH:mm', { locale: ru })}
                    </span>
                  </div>

                  {/* Type badge */}
                  <div className="flex items-center">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold ${
                      t.meeting_type?.includes('Финансовое')
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                        : t.meeting_type?.includes('HR')
                          ? 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300'
                          : t.meeting_type?.includes('Экстренное')
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                    }`}>
                      {getTypeBadge(t.meeting_type)}
                    </span>
                  </div>

                  {/* Duration */}
                  <div className="flex items-center">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {t.duration ? formatDuration(t.duration) : '—'}
                    </span>
                  </div>

                  {/* Speakers */}
                  <div className="flex items-center justify-center">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {t.speakers?.length || 0}
                    </span>
                  </div>

                  {/* Actions: rename + delete */}
                  <div className="flex flex-col items-center justify-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditingId(t.transcript_id); setEditTitle(t.title); }}
                      className="w-6 h-6 rounded-lg hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-blue-500 flex items-center justify-center transition-all opacity-0 group-hover:opacity-100 cursor-pointer"
                      title="Переименовать"
                      type="button"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setDeletingId(t.transcript_id); }}
                      className="w-6 h-6 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 flex items-center justify-center transition-all opacity-0 group-hover:opacity-100 cursor-pointer"
                      title="Удалить"
                      type="button"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                  </div>
                </div>
              )})}
            </div>
          </div>

          {/* Load more */}
          <div className="flex justify-center mt-8">
            {isLoading && allTranscripts.length > 0 ? (
              <LoadingSpinner text="Загрузка..." size="sm" />
            ) : hasMore ? (
              <button
                onClick={loadMore}
                className="px-6 py-3 rounded-xl bg-white dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-base-700 hover:shadow-md transition-all"
              >
                Загрузить ещё
              </button>
            ) : allTranscripts.length > 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Показаны все {allTranscripts.length} {allTranscripts.length === 1 ? 'совещание' : allTranscripts.length < 5 ? 'совещания' : 'совещаний'}
              </p>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
};