import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/context/AuthContext';
import { Navigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { TranscriptTableView, type TranscriptRow } from '@/components/transcriptions/TranscriptTableView';
import apiClient from '@/api/client';
import type { User } from '@/types/auth';

interface AdminStats {
  total_users: number;
  total_transcripts: number;
  total_duration: number;
}

interface UserTranscriptsResponse {
  items: {
    transcript_id: string;
    title: string;
    original_text: string;
    created_at: string;
    summary: string | null;
    speakers: string[];
    duration: number;
    parts_count: number;
  }[];
  total: number;
  user: { user_id: string; full_name: string; login: string; email: string };
  limit: number;
  offset: number;
}

type Tab = 'users' | 'transcripts';

// ── Вкладка «Пользователи» ──
function UsersTab({ users, stats, statsLoading }: {
  users: User[] | undefined; stats: AdminStats | undefined; statsLoading: boolean;
}) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newSurname, setNewSurname] = useState('');
  const [newName, setNewName] = useState('');
  const [newPatronymic, setNewPatronymic] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState<'user' | 'admin'>('user');

  const queryClient = useQueryClient();
  const invalidate = () => { queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }); queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] }); };

  const { mutate: createUser, isPending: isCreating } = useMutation({
    mutationFn: async (d: { username: string; password: string; surname: string; name: string; patronymic?: string; email: string; role: string }) =>
      (await apiClient.post('/admin/users', d)).data,
    onSuccess: () => { invalidate(); setShowAddForm(false); setNewUsername(''); setNewPassword(''); setNewSurname(''); setNewName(''); setNewPatronymic(''); setNewEmail(''); setNewRole('user'); }
  });

  const { mutate: deleteUser } = useMutation({
    mutationFn: async (id: string) => { await apiClient.delete(`/admin/users/${id}`); },
    onSuccess: invalidate,
  });

  const { mutate: updateUserRole } = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => { await apiClient.patch(`/admin/users/${userId}/role`, { role }); },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  });

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'Пользователей', value: stats?.total_users, bg: 'bg-blue-100 dark:bg-blue-900/30', icon: '👥' },
          { label: 'Транскрипций', value: stats?.total_transcripts, bg: 'bg-emerald-100 dark:bg-emerald-900/30', icon: '📄' },
          { label: 'Общее время', value: stats ? `${Math.round((stats.total_duration || 0) / 60)} мин` : null, bg: 'bg-indigo-100 dark:bg-indigo-900/30', icon: '⏱️' },
        ].map((s, i) => (
          <div key={i} className="bg-white dark:bg-dark-base-800 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700">
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-2xl ${s.bg} flex items-center justify-center shrink-0`}>
                <span className="text-xl">{s.icon}</span>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">{s.label}</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{statsLoading ? '...' : s.value ?? 0}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* User form toggle */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Пользователи</h2>
        <Button variant="secondary" onClick={() => setShowAddForm(v => !v)}>
          {showAddForm ? 'Закрыть' : 'Добавить пользователя'}
        </Button>
      </div>

      {showAddForm && (
        <div className="bg-white dark:bg-dark-base-800 rounded-2xl p-6 border border-gray-200 dark:border-dark-base-700">
          <form onSubmit={(e) => { e.preventDefault(); if (newUsername && newPassword && newSurname && newName && newEmail) createUser({
            username: newUsername, password: newPassword, surname: newSurname, name: newName, patronymic: newPatronymic || undefined, email: newEmail, role: newRole }); }}
            className="space-y-4"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { label: 'Логин', val: newUsername, set: setNewUsername, placeholder: 'username', required: true, type: 'text' },
                { label: 'Пароль', val: newPassword, set: setNewPassword, placeholder: '••••••••', required: true, type: 'password' },
                { label: 'Фамилия', val: newSurname, set: setNewSurname, placeholder: 'Иванов', required: true, type: 'text' },
                { label: 'Имя', val: newName, set: setNewName, placeholder: 'Иван', required: true, type: 'text' },
                { label: 'Отчество', val: newPatronymic, set: setNewPatronymic, placeholder: 'Иванович', required: false, type: 'text' },
                { label: 'Email', val: newEmail, set: setNewEmail, placeholder: 'ivan@example.com', required: true, type: 'email' },
              ].map((f, i) => (
                <div key={i}>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{f.label}</label>
                  <input type={f.type} value={f.val} onChange={(e) => f.set(e.target.value)}
                    className="w-full border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder={f.placeholder} required={f.required} />
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Роль</label>
                <select value={newRole} onChange={(e) => setNewRole(e.target.value as 'user' | 'admin')}
                  className="w-full border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
                  <option value="user">Пользователь</option>
                  <option value="admin">Администратор</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <Button type="submit" isLoading={isCreating} size="sm">Создать</Button>
              <Button variant="ghost" type="button" size="sm" onClick={() => setShowAddForm(false)}>Отмена</Button>
            </div>
          </form>
        </div>
      )}

      {/* Users table */}
      {!users ? (
        <LoadingSpinner text="Загрузка пользователей..." size="sm" />
      ) : users.length === 0 ? (
        <p className="text-center text-gray-500 py-8">Нет пользователей</p>
      ) : (
        <div className="bg-white dark:bg-dark-base-800 rounded-2xl border border-gray-200 dark:border-dark-base-700 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 dark:border-dark-base-700">
                <th className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-3">Пользователь</th>
                <th className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-3">Email</th>
                <th className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-3">Роль</th>
                <th className="text-right text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-3">Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-b border-gray-100 dark:border-dark-base-700 hover:bg-gray-50 dark:hover:bg-dark-base-700/50 transition-colors">
                  <td className="px-5 py-3.5">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">{u.full_name || u.username}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">@{u.username}</p>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-gray-600 dark:text-gray-300">{u.email || '—'}</td>
                  <td className="px-5 py-3.5">
                    <select value={u.role} onChange={(e) => updateUserRole({ userId: u.user_id, role: e.target.value })}
                      className="text-xs border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500">
                      <option value="user">Пользователь</option>
                      <option value="admin">Администратор</option>
                    </select>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button onClick={() => { if (confirm(`Удалить пользователя ${u.full_name || u.username}?`)) deleteUser(u.user_id); }}
                      className="text-xs text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 px-2 py-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer font-medium"
                    >Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Вкладка «Транскрипции» ──
function TranscriptsTab() {
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [userSearch, setUserSearch] = useState('');
  const [usersOpen, setUsersOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [actualSearchQuery, setActualSearchQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actualStartDate, setActualStartDate] = useState('');
  const [actualEndDate, setActualEndDate] = useState('');
  const [offset, setOffset] = useState(0);
  const [allTranscripts, setAllTranscripts] = useState<TranscriptRow[]>([]);

  const usersRef = useRef<HTMLDivElement>(null);
  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (usersRef.current && !usersRef.current.contains(e.target as Node)) setUsersOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const { data: allUsers } = useQuery<User[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await apiClient.get('/admin/users')).data,
  });

  const filteredUsers = useMemo(() => {
    if (!allUsers) return [];
    const q = userSearch.toLowerCase();
    return allUsers.filter(u =>
      u.full_name?.toLowerCase().includes(q) ||
      u.username?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q)
    );
  }, [allUsers, userSearch]);

  const selectedUser = allUsers?.find(u => u.user_id === selectedUserId);

  const { data: pageData, isLoading, isFetching } = useQuery<UserTranscriptsResponse>({
    queryKey: ['admin', 'transcripts', selectedUserId, offset, actualSearchQuery, actualStartDate, actualEndDate],
    queryFn: async () => {
      if (!selectedUserId) throw new Error('No user');
      let url = `/admin/users/${selectedUserId}/transcripts?limit=50&offset=${offset}`;
      if (actualSearchQuery) url += `&search=${encodeURIComponent(actualSearchQuery)}`;
      if (actualStartDate) url += `&start_date=${actualStartDate}`;
      if (actualEndDate) url += `&end_date=${actualEndDate}`;
      return (await apiClient.get(url)).data;
    },
    enabled: !!selectedUserId,
  });

  const total = pageData?.total ?? 0;
  const hasMore = allTranscripts.length < total;

  useEffect(() => {
    if (!pageData) return;
    const mapped: TranscriptRow[] = pageData.items.map(t => ({
      transcript_id: t.transcript_id,
      title: t.title,
      created_at: t.created_at,
      meeting_type: null,
      duration: t.duration,
      speakers: t.speakers,
      summary: t.summary,
      key_points: null,
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
  }, [pageData, offset]);

  const toISODate = (val: string): string => {
    const m = val.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    return m ? `${m[3]}-${m[2]}-${m[1]}` : val;
  };
  const toDisplayDate = (val: string): string => {
    const m = val.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : val;
  };

  const resetPagination = useCallback(() => { setOffset(0); setAllTranscripts([]); }, []);

  const selectUser = (uid: string) => {
    setSelectedUserId(uid);
    setUsersOpen(false);
    setUserSearch('');
    setSearchQuery(''); setActualSearchQuery('');
    setStartDate(''); setEndDate('');
    setActualStartDate(''); setActualEndDate('');
    resetPagination();
  };

  const applyFilters = useCallback(() => {
    if (!selectedUserId) return;
    setActualSearchQuery(searchQuery);
    setActualStartDate(toISODate(startDate));
    const isoEnd = toISODate(endDate);
    setActualEndDate(isoEnd ? `${isoEnd}T23:59:59` : '');
    resetPagination();
  }, [searchQuery, startDate, endDate, selectedUserId, resetPagination]);

  const clearFilters = useCallback(() => {
    setSearchQuery(''); setActualSearchQuery('');
    setStartDate(''); setEndDate('');
    setActualStartDate(''); setActualEndDate('');
    resetPagination();
  }, [resetPagination]);

  const handleDelete = useCallback(async (id: string) => {
    await apiClient.delete(`/admin/transcripts/${id}`);
    setAllTranscripts(prev => prev.filter(t => t.transcript_id !== id));
    queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
  }, [queryClient]);

  const handleRename = useCallback(async (id: string, title: string) => {
    await apiClient.put(`/transcripts/${id}/rename`, { title });
    setAllTranscripts(prev => prev.map(t => t.transcript_id === id ? { ...t, title } : t));
  }, []);

  const loadMore = useCallback(() => {
    if (!isFetching && hasMore) setOffset(prev => prev + PAGE_SIZE);
  }, [isFetching, hasMore]);

  const hasFilters = actualSearchQuery || actualStartDate || actualEndDate;
  const isFirstLoad = isLoading && allTranscripts.length === 0 && offset === 0;
  const PAGE_SIZE = 50;

  return (
    <div>
      {/* User selector */}
      <div className="relative mb-5" ref={usersRef}>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Пользователь</label>
        <button onClick={() => setUsersOpen(v => !v)}
          className="w-full flex items-center justify-between px-3 py-2.5 text-sm rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white hover:border-blue-300 dark:hover:border-blue-700 transition-colors cursor-pointer"
        >
          <span>{selectedUser ? `${selectedUser.full_name || selectedUser.username} (@${selectedUser.username})` : 'Выберите пользователя...'}</span>
          <svg className={`w-4 h-4 text-gray-400 transition-transform ${usersOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {usersOpen && (
          <div className="absolute top-full left-0 right-0 mt-1 z-20 bg-white dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 rounded-xl shadow-xl overflow-hidden">
            <div className="p-2">
              <input type="text" value={userSearch} onChange={(e) => setUserSearch(e.target.value)}
                placeholder="Поиск пользователей..."
                className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
                autoFocus />
            </div>
            <div className="max-h-48 overflow-y-auto">
              {filteredUsers.length === 0 ? (
                <p className="text-center text-xs text-gray-500 py-4">Ничего не найдено</p>
              ) : filteredUsers.map(u => (
                <button key={u.user_id} onClick={() => selectUser(u.user_id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left hover:bg-gray-50 dark:hover:bg-dark-base-700 transition-colors cursor-pointer ${
                    u.user_id === selectedUserId ? 'bg-blue-50 dark:bg-blue-900/15 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-200'
                  }`}
                >
                  <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                    {(u.full_name || u.username).charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 text-left">
                    <p className="font-medium truncate">{u.full_name || u.username}</p>
                    <p className="text-xs text-gray-400 truncate">@{u.username}</p>
                  </div>
                  {u.role === 'admin' && (
                    <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 shrink-0">admin</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Search + date filters (disabled until user selected) */}
      <div className="flex flex-wrap items-start gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
            placeholder="Поиск по названию..."
            disabled={!selectedUserId}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50"
          />
          {searchQuery && (
            <button onClick={() => { setSearchQuery(''); setActualSearchQuery(''); resetPagination(); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer text-xs">✕</button>
          )}
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none">🔍</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Дата:</span>
          <div className="relative">
            <input type="text" value={startDate} onChange={(e) => setStartDate(e.target.value)}
              placeholder="дд/мм/гггг" disabled={!selectedUserId}
              className="w-28 pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50"
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
              placeholder="дд/мм/гггг" disabled={!selectedUserId}
              className="w-28 pl-7 pr-2 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-dark-base-600 bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50"
            />
            <button type="button" onClick={() => endDateRef.current?.showPicker()}
              className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" strokeWidth="2"/><line x1="3" y1="10" x2="21" y2="10" strokeWidth="2"/><line x1="8" y1="2" x2="8" y2="6" strokeWidth="2"/><line x1="16" y1="2" x2="16" y2="6" strokeWidth="2"/></svg>
            </button>
            <input ref={endDateRef} type="date" onChange={(e) => { if (e.target.value) setEndDate(toDisplayDate(e.target.value)); }} className="sr-only" />
          </div>
          <button onClick={applyFilters} disabled={!selectedUserId}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white transition-colors cursor-pointer">OK</button>
          {hasFilters && (
            <button onClick={clearFilters}
              className="px-3 py-1.5 text-xs font-medium rounded-lg text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
            >✕ Сбросить</button>
          )}
        </div>
      </div>

      {/* Transcript table */}
      {!selectedUserId ? (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-900/20 dark:to-indigo-900/20 flex items-center justify-center mx-auto mb-3">
            <span className="text-3xl">👆</span>
          </div>
          <p className="text-base font-semibold text-gray-900 dark:text-white mb-1">Выберите пользователя</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Чтобы просмотреть его транскрипции</p>
        </div>
      ) : isFirstLoad ? (
        <div className="flex justify-center py-20">
          <LoadingSpinner text="Загрузка транскрипций..." size="sm" />
        </div>
      ) : (
        <TranscriptTableView
          transcripts={allTranscripts}
          total={total}
          isLoading={isFetching}
          hasFilters={hasFilters}
          onDelete={handleDelete}
          onRename={handleRename}
          onLoadMore={loadMore}
          onRefresh={clearFilters}
          emptyMessage={hasFilters ? 'Ничего не найдено' : 'У пользователя нет транскрипций'}
          emptyHint={hasFilters ? 'Попробуйте изменить параметры поиска' : ''}
        />
      )}
    </div>
  );
}

// ── Главный компонент ──
export const AdminPage = () => {
  const { user, isAuthenticated } = useAuth();
  if (!isAuthenticated || user?.role !== 'admin') return <Navigate to="/" replace />;

  const [activeTab, setActiveTab] = useState<Tab>('users');

  const { data: stats, isLoading: statsLoading } = useQuery<AdminStats>({
    queryKey: ['admin', 'stats'],
    queryFn: async () => (await apiClient.get('/admin/stats')).data,
  });

  const { data: users, isLoading: usersLoading, error: usersError } = useQuery<User[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await apiClient.get('/admin/users')).data,
  });

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'users', label: 'Пользователи', icon: '👥' },
    { key: 'transcripts', label: 'Транскрипции', icon: '📄' },
  ];

  return (
    <div className="max-w-7xl mx-auto mt-6 pb-12">
      <h1 className="text-4xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight mb-6">
        Панель администратора
      </h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-gray-100 dark:bg-dark-base-800 rounded-xl w-fit">
        {tabs.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === tab.key
                ? 'bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {activeTab === 'users' && (
        usersLoading ? <div className="flex justify-center py-12"><LoadingSpinner text="Загрузка..." size="sm" /></div>
        : usersError ? <ErrorMessage message="Не удалось загрузить данные" />
        : <UsersTab users={users} stats={stats} statsLoading={statsLoading} />
      )}

      {activeTab === 'transcripts' && <TranscriptsTab />}
    </div>
  );
};
