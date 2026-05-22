import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranscripts } from '@/hooks/useTranscripts';
import { transcriptsApi } from '@/api/transcripts';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useSidebar } from '@/context/SidebarContext';
import type { Transcript } from '@/types/transcript';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const PAGE_SIZE = 30;

const getTypeIcon = (mt: string | undefined | null): string => {
  if (mt?.includes('Оперативное')) return '📊';
  if (mt?.includes('Стратегическое')) return '🎯';
  if (mt?.includes('Финансовое')) return '💰';
  if (mt?.includes('HR')) return '👥';
  if (mt?.includes('Экстренное')) return '🚨';
  return '📋';
};

export const TranscriptionHistoryPanel = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isOpen, toggle } = useSidebar();

  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [actualSearchQuery, setActualSearchQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actualStartDate, setActualStartDate] = useState('');
  const [actualEndDate, setActualEndDate] = useState('');
  const [allTranscripts, setAllTranscripts] = useState<Transcript[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);

  const { transcripts, isLoading, error, total, refetch } = useTranscripts({
    limit: PAGE_SIZE,
    offset,
    searchQuery: actualSearchQuery || undefined,
    startDate: actualStartDate || undefined,
    endDate: actualEndDate || undefined,
  });

  // Refs to avoid stale closures in scroll handler
  const isLoadingRef = useRef(isLoading);
  isLoadingRef.current = isLoading;
  const hasMoreRef = useRef(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const hasMore = useMemo(() => allTranscripts.length < total, [allTranscripts.length, total]);
  hasMoreRef.current = hasMore;

  // Accumulate transcripts — reset on filter change
  const prevOffsetRef = useRef(offset);
  useEffect(() => {
    if (isLoading || transcripts.length === 0) return;

    if (offset === 0) {
      // New search/filter — full replace
      setAllTranscripts(transcripts);
    } else if (offset > prevOffsetRef.current) {
      // Scrolled forward — append
      setAllTranscripts(prev => {
        const existingIds = new Set(prev.map(t => t.transcript_id));
        const newOnes = transcripts.filter(t => !existingIds.has(t.transcript_id));
        if (newOnes.length === 0) return prev;
        return [...prev, ...newOnes];
      });
    }
    prevOffsetRef.current = offset;
  }, [transcripts, isLoading, offset]);

  // Determine active transcript id from URL
  const activeId = location.pathname.startsWith('/analysis/')
    ? location.pathname.split('/analysis/')[1]
    : null;

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

  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);

  const resetPagination = useCallback(() => {
    setOffset(0);
    setAllTranscripts([]);
    prevOffsetRef.current = 0;
  }, []);

  const applyFilters = useCallback(() => {
    setActualSearchQuery(searchQuery);
    setActualStartDate(toISODate(startDate));
    setActualEndDate(toISODate(endDate));
    resetPagination();
  }, [searchQuery, startDate, endDate, resetPagination]);

  const clearFilters = useCallback(() => {
    setSearchQuery('');
    setActualSearchQuery('');
    setStartDate('');
    setEndDate('');
    setActualStartDate('');
    setActualEndDate('');
    resetPagination();
  }, [resetPagination]);

  const handleDelete = async (id: string) => {
    try {
      await transcriptsApi.delete(id);
      setDeletingId(null);
      setAllTranscripts(prev => prev.filter(t => t.transcript_id !== id));
      refetch();
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  const handleRename = async (id: string) => {
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
  };

  const handleTranscriptClick = useCallback((id: string) => {
    navigate(`/analysis/${id}`);
  }, [navigate]);

  // ── Infinite scroll via scroll handler ──
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    if (isLoadingRef.current || !hasMoreRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = el;
    // Trigger load when within 400px of bottom
    if (scrollHeight - scrollTop - clientHeight < 400) {
      setOffset(prev => prev + PAGE_SIZE);
    }
  }, []);

  const hasFilters = actualSearchQuery || actualStartDate || actualEndDate;

  // Whether we're still loading the very first batch
  const isFirstLoad = isLoading && allTranscripts.length === 0 && offset === 0;

  return (
    <>
      {/* Toggle button – always visible at sidebar edge */}
      <button
        onClick={toggle}
        className={`fixed top-1/2 -translate-y-1/2 z-40 w-7 h-14 bg-white dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 rounded-r-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center cursor-pointer ${
          isOpen ? 'left-[340px] border-l-0' : 'left-0 border-l-0'
        }`}
        title={isOpen ? 'Скрыть историю' : 'Показать историю'}
        type="button"
      >
        <span className={`text-lg transition-transform duration-300 ${isOpen ? '' : 'rotate-180'}`}>
          ◀
        </span>
      </button>

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-16 bottom-0 z-30 w-[340px] bg-white dark:bg-dark-base-900 border-r border-gray-200 dark:border-dark-base-700 shadow-xl transition-all duration-300 flex flex-col ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-base-700 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center shadow-sm">
              <span className="text-base">📋</span>
            </div>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">История</h3>
          </div>
          <div className="flex items-center gap-1">
            {total > 0 && (
              <span className="text-xs text-gray-400 dark:text-gray-500 font-medium bg-gray-100 dark:bg-dark-base-800 px-2 py-0.5 rounded-full">
                {total}
              </span>
            )}
            <button
              onClick={toggle}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-800 transition-colors cursor-pointer"
              title="Закрыть"
              type="button"
            >
              <span className="text-sm">✕</span>
            </button>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-base-700 flex-shrink-0 space-y-2">
          {/* Search */}
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
              placeholder="Поиск..."
              className="w-full pl-8 pr-8 py-2 text-sm rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
            />
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(''); setActualSearchQuery(''); resetPagination(); }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
                type="button"
              >
                ✕
              </button>
            )}
          </div>

          {/* Date range + Apply */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <div className="relative flex-1 min-w-0">
              <input
                type="text"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder="дд/мм/гггг"
                className="w-full pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
              />
              <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none text-xs">📅</span>
              <input
                ref={startDateRef}
                type="date"
                onChange={(e) => { if (e.target.value) setStartDate(toDisplayDate(e.target.value)); }}
                className="absolute right-1 top-1/2 -translate-y-1/2 w-6 h-6 opacity-0 cursor-pointer"
              />
            </div>
            <span className="text-gray-400 dark:text-gray-500 text-xs flex-shrink-0">—</span>
            <div className="relative flex-1 min-w-0">
              <input
                type="text"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="дд/мм/гггг"
                className="w-full pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
              />
              <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none text-xs">📅</span>
              <input
                ref={endDateRef}
                type="date"
                onChange={(e) => { if (e.target.value) setEndDate(toDisplayDate(e.target.value)); }}
                className="absolute right-1 top-1/2 -translate-y-1/2 w-6 h-6 opacity-0 cursor-pointer"
              />
            </div>
            <button
              onClick={applyFilters}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-violet-500 hover:bg-violet-600 text-white transition-colors flex-shrink-0 cursor-pointer"
              type="button"
            >
              OK
            </button>
          </div>

          {/* Active filters indicator & clear */}
          {hasFilters && (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-violet-600 dark:text-violet-400 font-medium">
                Фильтр активен
              </span>
              <button
                onClick={clearFilters}
                className="text-[10px] text-gray-400 hover:text-red-500 transition-colors cursor-pointer"
                type="button"
              >
                Сбросить
              </button>
            </div>
          )}
        </div>

        {/* Transcript list — GPT-style infinite scroll */}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto overflow-x-hidden overscroll-contain"
        >
          {/* Initial loading skeleton */}
          {isFirstLoad ? (
            <div className="space-y-1 px-2 pt-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-start gap-2.5 px-2 py-3 animate-pulse">
                  <div className="w-2 h-2 rounded-full bg-gray-200 dark:bg-dark-base-700 mt-1.5 flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3.5 bg-gray-200 dark:bg-dark-base-700 rounded w-3/4" />
                    <div className="h-2.5 bg-gray-100 dark:bg-dark-base-750 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="p-4">
              <ErrorMessage message="Ошибка загрузки" />
            </div>
          ) : !allTranscripts.length ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-100 to-purple-100 dark:from-violet-900/30 dark:to-purple-900/30 flex items-center justify-center mx-auto mb-3">
                <span className="text-2xl">📝</span>
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white mb-1">
                {hasFilters ? 'Ничего не найдено' : 'Пока пусто'}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {hasFilters
                  ? 'Попробуйте изменить параметры поиска'
                  : 'Транскрипции появятся здесь'}
              </p>
              {hasFilters && (
                <button
                  onClick={clearFilters}
                  className="mt-3 px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/50 transition-colors cursor-pointer"
                  type="button"
                >
                  Сбросить фильтры
                </button>
              )}
            </div>
          ) : (
            <div>
              {allTranscripts.map((t) => {
                const isActive = t.transcript_id === activeId;
                const isDeleting = deletingId === t.transcript_id;
                const isEditing = editingId === t.transcript_id;
                const isSaving = savingId === t.transcript_id;

                return (
                  <div
                    key={t.transcript_id}
                    className={`group relative px-4 py-3 transition-colors cursor-pointer border-l-2 ${
                      isActive
                        ? 'bg-violet-50 dark:bg-violet-900/15 border-l-violet-500'
                        : 'border-l-transparent hover:bg-gray-50 dark:hover:bg-dark-base-800/60'
                    } ${isDeleting ? 'opacity-50' : ''}`}
                    onClick={() => handleTranscriptClick(t.transcript_id)}
                  >
                    {/* Delete overlay */}
                    {isDeleting && (
                      <div
                        className="absolute inset-0 bg-red-50/80 dark:bg-red-900/20 z-10 flex items-center justify-center rounded-lg"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex gap-2">
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); handleDelete(t.transcript_id); }}
                          >
                            Удалить
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); setDeletingId(null); }}
                          >
                            Отмена
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="flex items-start gap-2.5">
                      {/* GPT-style dot indicator */}
                      <span className="text-[10px] mt-0.5 flex-shrink-0 leading-none opacity-60">
                        {getTypeIcon(t.meeting_type)}
                      </span>

                      <div className="flex-1 min-w-0">
                        {/* Title + inline rename */}
                        {isEditing ? (
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleRename(t.transcript_id);
                                if (e.key === 'Escape') setEditingId(null);
                              }}
                              className="flex-1 min-w-0 px-1.5 py-0.5 text-xs border border-gray-300 dark:border-dark-base-600 rounded bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:outline-none"
                              autoFocus
                            />
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRename(t.transcript_id); }}
                              className="w-5 h-5 rounded bg-green-500 hover:bg-green-600 text-white flex items-center justify-center flex-shrink-0 transition-colors text-[9px]"
                              title="Сохранить"
                              type="button"
                            >
                              {isSaving ? '…' : '✓'}
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); setEditingId(null); }}
                              className="w-5 h-5 rounded bg-gray-200 dark:bg-dark-base-700 hover:bg-gray-300 dark:hover:bg-dark-base-600 text-gray-700 dark:text-gray-300 flex items-center justify-center flex-shrink-0 transition-colors text-[9px]"
                              title="Отмена"
                              type="button"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-1">
                            <h4 className={`text-sm leading-tight truncate ${
                              isActive
                                ? 'font-semibold text-violet-700 dark:text-violet-300'
                                : 'font-medium text-gray-900 dark:text-white'
                            }`}>
                              {t.title}
                            </h4>
                            {/* Hover actions */}
                            <div
                              className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                onClick={(e) => { e.stopPropagation(); setEditingId(t.transcript_id); setEditTitle(t.title); }}
                                className="w-5 h-5 rounded hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex items-center justify-center transition-colors text-[10px]"
                                title="Переименовать"
                                type="button"
                              >
                                ✏️
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); setDeletingId(t.transcript_id); }}
                                className="w-5 h-5 rounded hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-red-500 flex items-center justify-center transition-colors text-[10px]"
                                title="Удалить"
                                type="button"
                              >
                                🗑️
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Date */}
                        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                          {format(new Date(t.created_at), 'd MMM yyyy, HH:mm', { locale: ru })}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Loading more indicator */}
              {isLoading && allTranscripts.length > 0 && (
                <div className="flex justify-center py-4">
                  <LoadingSpinner text="" size={'sm'} />
                </div>
              )}

              {/* End of list marker */}
              {!hasMore && allTranscripts.length > 0 && !isLoading && (
                <div className="text-center py-4">
                  <span className="text-[10px] text-gray-300 dark:text-gray-600">
                    Загружено {total} транскрипций
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Spacer for main content when sidebar is open */}
      {isOpen && <div className="w-[340px] flex-shrink-0" />}
    </>
  );
};
