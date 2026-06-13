import { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

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

const formatDuration = (minutes: number): string => {
  const totalSeconds = Math.round(minutes * 60);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
};

export interface TranscriptRow {
  transcript_id: string;
  title: string;
  created_at: string;
  meeting_type?: string | null;
  duration?: number;
  speakers?: string[];
  summary?: string | null;
  key_points?: string[] | null;
}

type SortField = 'date' | 'title' | 'type' | 'duration' | 'speakers';
type SortDir = 'asc' | 'desc';

interface Props {
  transcripts: TranscriptRow[];
  total: number;
  isLoading: boolean;
  hasFilters?: boolean;
  onDelete: (id: string) => Promise<void>;
  onRename: (id: string, title: string) => Promise<void>;
  onLoadMore?: () => void;
  onRefresh?: () => void;
  emptyMessage?: string;
  emptyHint?: string;
}

export const TranscriptTableView = ({
  transcripts,
  total,
  isLoading,
  hasFilters,
  onDelete,
  onRename,
  onLoadMore,
  onRefresh,
  emptyMessage = 'Ещё нет записей',
  emptyHint = '',
}: Props) => {
  const navigate = useNavigate();
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await onDelete(id);
      setDeletingId(null);
    } catch (err) {
      console.error('Delete error:', err);
    }
  }, [onDelete]);

  const handleRename = useCallback(async (id: string) => {
    if (!editTitle.trim()) return;
    setSavingId(id);
    try {
      await onRename(id, editTitle.trim());
      setEditingId(null);
    } catch (err) {
      console.error('Rename error:', err);
    } finally {
      setSavingId(null);
    }
  }, [editTitle, onRename]);

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

  const filtered = useMemo(() => {
    const items = [...transcripts];
    items.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'date': cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime(); break;
        case 'title': cmp = a.title.localeCompare(b.title); break;
        case 'type': cmp = (a.meeting_type || '').localeCompare(b.meeting_type || ''); break;
        case 'duration': cmp = (a.duration || 0) - (b.duration || 0); break;
        case 'speakers': cmp = (a.speakers?.length || 0) - (b.speakers?.length || 0); break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });
    return items;
  }, [transcripts, sortField, sortDir]);

  const hasMore = transcripts.length < total;

  if (transcripts.length === 0 && !isLoading) {
    return (
      <div className="text-center py-16">
        <div className="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-3">
          <span className="text-3xl">📋</span>
        </div>
        <p className="text-base font-semibold text-gray-900 dark:text-white mb-1">{emptyMessage}</p>
        {emptyHint && <p className="text-sm text-gray-500 dark:text-gray-400">{emptyHint}</p>}
        {hasFilters && onRefresh && (
          <button onClick={onRefresh} className="mt-3 px-4 py-2 text-sm font-medium rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors cursor-pointer">
            Сбросить фильтры
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-base-900 rounded-2xl border border-gray-200 dark:border-dark-base-700 overflow-hidden shadow-sm">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_120px_90px_80px_45px_45px] gap-3 px-6 py-3 bg-gray-50 dark:bg-dark-base-800 border-b border-gray-200 dark:border-dark-base-700 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        <button onClick={() => toggleSort('title')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors cursor-pointer">
          Название <SortArrow field="title" />
        </button>
        <button onClick={() => toggleSort('date')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors cursor-pointer">
          Дата <SortArrow field="date" />
        </button>
        <button onClick={() => toggleSort('type')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors cursor-pointer">
          Тип <SortArrow field="type" />
        </button>
        <button onClick={() => toggleSort('duration')} className="flex items-center text-left hover:text-gray-700 dark:hover:text-gray-300 transition-colors cursor-pointer">
          Длит. <SortArrow field="duration" />
        </button>
        <button onClick={() => toggleSort('speakers')} className="flex items-center justify-center hover:text-gray-700 dark:hover:text-gray-300 transition-colors cursor-pointer">
          <SortArrow field="speakers" /> 🗣
        </button>
        <span className="text-center" />
      </div>

      {/* Table body */}
      <div className="divide-y divide-gray-100 dark:divide-dark-base-800">
        {filtered.map((t) => {
          const isDeleting = deletingId === t.transcript_id;
          return (
            <div key={t.transcript_id} className="relative grid grid-cols-[1fr_120px_90px_80px_45px_45px] gap-3 px-6 py-4 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors group">
              {isDeleting && (
                <div className="absolute inset-0 bg-red-50/90 dark:bg-red-900/25 z-10 flex items-center justify-center rounded-lg" onClick={(e) => e.stopPropagation()}>
                  <div className="flex gap-2">
                    <Button variant="danger" size="sm" onClick={(e) => { e.stopPropagation(); handleDelete(t.transcript_id); }}>Удалить</Button>
                    <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); setDeletingId(null); }}>Отмена</Button>
                  </div>
                </div>
              )}

              {/* Title + summary */}
              <button onClick={() => { if (editingId !== t.transcript_id) navigate(`/analysis/${t.transcript_id}`); }}
                className="min-w-0 text-left cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{getTypeIcon(t.meeting_type)}</span>
                  {editingId === t.transcript_id ? (
                    <div className="flex items-center gap-1 flex-1" onClick={(e) => e.stopPropagation()}>
                      <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleRename(t.transcript_id); if (e.key === 'Escape') setEditingId(null); }}
                        className="flex-1 min-w-0 px-1.5 py-0.5 text-sm border border-gray-300 dark:border-dark-base-600 rounded bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                        autoFocus
                      />
                      <button onClick={(e) => { e.stopPropagation(); handleRename(t.transcript_id); }}
                        className="w-6 h-6 rounded bg-green-500 hover:bg-green-600 text-white flex items-center justify-center shrink-0 transition-colors text-[10px] cursor-pointer"
                      >{savingId === t.transcript_id ? '…' : '✓'}</button>
                      <button onClick={(e) => { e.stopPropagation(); setEditingId(null); }}
                        className="w-6 h-6 rounded bg-gray-200 dark:bg-dark-base-700 hover:bg-gray-300 dark:hover:bg-dark-base-600 text-gray-700 dark:text-gray-300 flex items-center justify-center shrink-0 transition-colors text-[10px] cursor-pointer"
                      >✕</button>
                    </div>
                  ) : (
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                      {t.title}
                    </h3>
                  )}
                </div>
                {t.summary && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2 leading-relaxed">{t.summary}</p>
                )}
                {t.key_points && t.key_points.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {t.key_points.slice(0, 3).map((kp, i) => (
                      <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-md bg-gray-100 dark:bg-dark-base-800 text-[10px] text-gray-600 dark:text-gray-400 font-medium">
                        {kp.length > 40 ? kp.slice(0, 40) + '...' : kp}
                      </span>
                    ))}
                    {t.key_points.length > 3 && (
                      <span className="text-[10px] text-gray-400 dark:text-gray-500">+{t.key_points.length - 3}</span>
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
                }`}>{getTypeBadge(t.meeting_type)}</span>
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

              {/* Actions */}
              <div className="flex flex-col items-center justify-center gap-1">
                <button onClick={(e) => { e.stopPropagation(); setEditingId(t.transcript_id); setEditTitle(t.title); }}
                  className="w-6 h-6 rounded hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex items-center justify-center transition-colors text-[10px] cursor-pointer"
                  title="Переименовать">✏️</button>
                <button onClick={(e) => { e.stopPropagation(); setDeletingId(t.transcript_id); }}
                  className="w-6 h-6 rounded hover:bg-gray-200 dark:hover:bg-dark-base-700 text-gray-400 hover:text-red-500 flex items-center justify-center transition-colors text-[10px] cursor-pointer"
                  title="Удалить">🗑️</button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Load more */}
      {hasMore && (
        <div className="px-6 py-4 text-center border-t border-gray-100 dark:border-dark-base-800">
          <button onClick={onLoadMore}
            className="px-6 py-2 text-sm font-medium rounded-xl bg-gray-100 dark:bg-dark-base-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-dark-base-700 transition-colors cursor-pointer"
            disabled={isLoading}
          >
            {isLoading ? 'Загрузка...' : `Загрузить ещё (${transcripts.length} из ${total})`}
          </button>
        </div>
      )}

      {!hasMore && transcripts.length > 0 && (
        <div className="px-6 py-3 text-center border-t border-gray-100 dark:border-dark-base-800">
          <span className="text-xs text-gray-400 dark:text-gray-500">Всего {total} записей</span>
        </div>
      )}
    </div>
  );
};
