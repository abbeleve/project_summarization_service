import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useNavigate, useLocation, NavLink } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/context/ThemeContext';
import { useTranscripts } from '@/hooks/useTranscripts';
import { transcriptsApi } from '@/api/transcripts';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import type { Transcript } from '@/types/transcript';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const PAGE_SIZE = 30;

type DateGroup = 'today' | 'week' | 'month' | 'older';

const getDateGroup = (dateStr: string): DateGroup => {
  const now = new Date();
  const date = new Date(dateStr);

  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  const diffDays = Math.floor((today.getTime() - target.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'today';
  if (diffDays < 7) return 'week';
  if (diffDays < 30) return 'month';
  return 'older';
};

const GROUP_LABELS: Record<DateGroup, string> = {
  today: 'Сегодня',
  week: '7 дней',
  month: '30 дней',
  older: 'Ранее',
};

const GROUP_ORDER: DateGroup[] = ['today', 'week', 'month', 'older'];

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
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const queryClient = useQueryClient();
  const [listExpanded, setListExpanded] = useState(true);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

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
    const isoEnd = toISODate(endDate);
    setActualEndDate(isoEnd ? `${isoEnd}T23:59:59` : '');
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

  const handleLogout = () => {
    logout(() => queryClient.clear());
    navigate('/login');
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  // Group transcripts by date
  const grouped = useMemo(() => {
    const groups: Record<DateGroup, Transcript[]> = { today: [], week: [], month: [], older: [] };
    for (const t of allTranscripts) {
      const group = getDateGroup(t.created_at);
      groups[group].push(t);
    }
    return groups;
  }, [allTranscripts]);

  return (
    <>
      {/* Sidebar — always visible */}
      <aside className="fixed left-0 top-0 bottom-0 z-[60] w-[340px] bg-white dark:bg-dark-base-900 border-r border-gray-200 dark:border-dark-base-700 shadow-xl flex flex-col">
        {/* Top section: Meeting Insight + nav */}
        <div className="flex flex-col px-4 pt-4 pb-2 border-b border-gray-200 dark:border-dark-base-700 flex-shrink-0">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">
            Meeting Insight
          </h2>
          <nav className="flex flex-col gap-0.5">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2.5 rounded-lg text-base font-medium transition-all ${
                  isActive
                    ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 shadow-md'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-800 hover:text-gray-900 dark:hover:text-white'
                }`
              }
            >
              <span>Главная</span>
            </NavLink>
            <NavLink
              to="/new-analysis"
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2.5 rounded-lg text-base font-medium transition-all ${
                  isActive
                    ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 shadow-md'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-800 hover:text-gray-900 dark:hover:text-white'
                }`
              }
            >
              <span>Новый анализ</span>
            </NavLink>
            <NavLink
              to="/meeting-bot"
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2.5 rounded-lg text-base font-medium transition-all ${
                  isActive
                    ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 shadow-md'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-800 hover:text-gray-900 dark:hover:text-white'
                }`
              }
            >
              <span>Meeting Bot</span>
            </NavLink>
          </nav>
        </div>

        {/* Header — click to collapse/expand list */}
        <div
          onClick={() => setListExpanded(v => !v)}
          className="flex items-center justify-between pl-7 pr-4 py-2.5 flex-shrink-0 cursor-pointer select-none hover:bg-gray-50 dark:hover:bg-dark-base-800/60 transition-colors"
        >
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-gray-900 dark:text-white">История</h3>
            <span
              className={`text-xs text-gray-400 transition-transform duration-300 ${
                listExpanded ? '' : 'rotate-180'
              }`}
            >
              ▼
            </span>
          </div>
          <div className="flex items-center gap-1">
            {total > 0 && (
              <span className="text-xs text-gray-400 dark:text-gray-500 font-medium bg-gray-100 dark:bg-dark-base-800 px-2 py-0.5 rounded-full">
                {total}
              </span>
            )}
          </div>
        </div>

        {/* Collapsible content wrapper — always takes flex-1 to keep profile at bottom */}
        <div className={`flex-1 min-h-0 flex flex-col ${listExpanded ? '' : 'overflow-hidden'}`}>
          {/* Search & Filters */}
          {listExpanded && (
            <div className="px-3 py-2 flex-shrink-0 space-y-2">
              {/* Search */}
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
                  placeholder="Поиск..."
                  className="w-full pl-8 pr-8 py-2 text-sm rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
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
                    className="w-full pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => startDateRef.current?.showPicker()}
                    className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors text-xs cursor-pointer"
                  >
                    📅
                  </button>
                  <input
                    ref={startDateRef}
                    type="date"
                    onChange={(e) => { if (e.target.value) setStartDate(toDisplayDate(e.target.value)); }}
                    className="sr-only"
                  />
                </div>
                <span className="text-gray-400 dark:text-gray-500 text-xs flex-shrink-0">—</span>
                <div className="relative flex-1 min-w-0">
                  <input
                    type="text"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    placeholder="дд/мм/гггг"
                    className="w-full pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => endDateRef.current?.showPicker()}
                    className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors text-xs cursor-pointer"
                  >
                    📅
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
                  className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-blue-500 hover:bg-blue-600 text-white transition-colors flex-shrink-0 cursor-pointer"
                  type="button"
                >
                  OK
                </button>
              </div>

              {/* Active filters indicator & clear */}
              {hasFilters && (
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-blue-600 dark:text-blue-400 font-medium">
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
          )}

          {/* Transcript list */}
          {listExpanded && (
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
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-100 to-blue-100 dark:from-blue-900/30 dark:to-blue-900/30 flex items-center justify-center mx-auto mb-3">
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
                    className="mt-3 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors cursor-pointer"
                    type="button"
                  >
                    Сбросить фильтры
                  </button>
                )}
              </div>
            ) : (
              <div>
                {GROUP_ORDER.map(groupKey => {
                  const items = grouped[groupKey];
                  if (items.length === 0) return null;
                  return (
                    <div key={groupKey}>
                      <div className="sticky top-0 z-10 px-4 py-2 bg-white/90 dark:bg-dark-base-900/90 backdrop-blur-sm">
                        <span className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          {GROUP_LABELS[groupKey]}
                        </span>
                      </div>
                      {items.map((t) => {
                        const isActive = t.transcript_id === activeId;
                        const isDeleting = deletingId === t.transcript_id;
                        const isEditing = editingId === t.transcript_id;
                        const isSaving = savingId === t.transcript_id;

                        return (
                          <div
                            key={t.transcript_id}
                            className={`group relative px-4 py-3 transition-colors cursor-pointer border-l-2 ${
                              isActive
                                ? 'bg-blue-50 dark:bg-blue-900/15 border-l-blue-500'
                                : 'border-l-transparent hover:bg-gray-50 dark:hover:bg-dark-base-800/60'
                            } ${isDeleting ? 'opacity-50' : ''}`}
                            onClick={() => handleTranscriptClick(t.transcript_id)}
                          >
                            {isDeleting && (
                              <div
                                className="absolute inset-0 bg-red-50/80 dark:bg-red-900/20 z-10 flex items-center justify-center rounded-lg"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <div className="flex gap-2">
                                  <Button variant="danger" size="sm" onClick={(e) => { e.stopPropagation(); handleDelete(t.transcript_id); }}>Удалить</Button>
                                  <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); setDeletingId(null); }}>Отмена</Button>
                                </div>
                              </div>
                            )}
                            <div className="flex items-start gap-2.5">
                              <span className="text-[10px] mt-0.5 flex-shrink-0 leading-none opacity-60">{getTypeIcon(t.meeting_type)}</span>
                              <div className="flex-1 min-w-0">
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
                                      className="flex-1 min-w-0 px-1.5 py-0.5 text-xs border border-gray-300 dark:border-dark-base-600 rounded bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                      autoFocus
                                    />
                                    <button onClick={(e) => { e.stopPropagation(); handleRename(t.transcript_id); }} className="w-5 h-5 rounded bg-green-500 hover:bg-green-600 text-white flex items-center justify-center flex-shrink-0 transition-colors text-[9px]" title="Сохранить" type="button">{isSaving ? '…' : '✓'}</button>
                                    <button onClick={(e) => { e.stopPropagation(); setEditingId(null); }} className="w-5 h-5 rounded bg-gray-200 dark:bg-dark-base-700 hover:bg-gray-300 dark:hover:bg-dark-base-600 text-gray-700 dark:text-gray-300 flex items-center justify-center flex-shrink-0 transition-colors text-[9px]" title="Отмена" type="button">✕</button>
                                  </div>
                                ) : (
                                  <div className="flex items-start justify-between gap-1">
                                    <h4 className={`text-sm leading-tight truncate ${isActive ? 'font-semibold text-blue-700 dark:text-blue-300' : 'font-medium text-gray-900 dark:text-white'}`}>{t.title}</h4>
                                    <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                                      <button onClick={(e) => { e.stopPropagation(); setEditingId(t.transcript_id); setEditTitle(t.title); }} className="w-5 h-5 rounded hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex items-center justify-center transition-colors text-[10px]" title="Переименовать" type="button">✏️</button>
                                      <button onClick={(e) => { e.stopPropagation(); setDeletingId(t.transcript_id); }} className="w-5 h-5 rounded hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-red-500 flex items-center justify-center transition-colors text-[10px]" title="Удалить" type="button">🗑️</button>
                                    </div>
                                  </div>
                                )}
                                <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">{format(new Date(t.created_at), 'd MMM yyyy, HH:mm', { locale: ru })}</p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
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
          )}
        </div>

        {/* Bottom: profile */}
        <div className="relative flex-shrink-0 border-t border-gray-200 dark:border-dark-base-700" ref={profileRef}>
          <button
            onClick={() => setProfileOpen(v => !v)}
            className="flex items-center gap-2 w-full px-4 py-3 pb-5 bg-white dark:bg-dark-base-900 hover:bg-gray-50 dark:hover:bg-dark-base-800 transition-colors cursor-pointer"
            type="button"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center shadow-md overflow-hidden flex-shrink-0">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <span className="text-sm font-bold text-white">
                  {user?.full_name?.charAt(0).toUpperCase() || 'U'}
                </span>
              )}
            </div>
            <div className="flex-1 text-left min-w-0">
              <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                {user?.full_name || 'Пользователь'}
              </p>
            </div>
            <svg
              className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform flex-shrink-0 ${profileOpen ? 'rotate-180' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown — opens upward */}
          {profileOpen && (
            <div className="absolute bottom-full left-0 right-0 mb-1 mx-2 bg-white dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 rounded-xl shadow-xl py-2 z-50">
              <div className="px-4 py-2 border-b border-gray-100 dark:border-dark-base-700">
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{user?.full_name || 'Пользователь'}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {user?.role === 'admin' ? 'Администратор' : 'Пользователь'}
                </p>
              </div>
              <button
                onClick={() => { toggleTheme(); setProfileOpen(false); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-base-700 transition-colors cursor-pointer"
                type="button"
              >
                <span className="text-lg">{theme === 'dark' ? '☀️' : '🌙'}</span>
                <span>{theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}</span>
              </button>
              <NavLink
                to="/profile"
                onClick={() => setProfileOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-base-700 transition-colors"
              >
                <span className="text-lg">👤</span>
                <span>Профиль</span>
              </NavLink>
              <NavLink
                to="/settings"
                onClick={() => setProfileOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-base-700 transition-colors"
              >
                <span className="text-lg">⚙️</span>
                <span>Настройки</span>
              </NavLink>
              <div className="border-t border-gray-100 dark:border-dark-base-700 my-1" />
              <button
                onClick={() => { setProfileOpen(false); handleLogout(); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
                type="button"
              >
                <span className="text-lg">🚪</span>
                <span>Выйти</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Spacer for main content — always active since sidebar is always fixed */}
      <div className="w-[340px] flex-shrink-0" />
    </>
  );
};
