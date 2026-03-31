// src/pages/AdminPage.tsx
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/context/AuthContext';
import { Navigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import apiClient from '@/api/client';
import type { User } from '@/types/auth';

interface AdminStats {
  total_users: number;
  total_transcripts: number;
  total_duration: number;
}

export const AdminPage = () => {
  const { user, isAuthenticated } = useAuth();
  
  if (!isAuthenticated || user?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  const [showAddForm, setShowAddForm] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'user' | 'admin'>('user');

  const {  data: users, isLoading: usersLoading, error: usersError } = useQuery<User[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => {
      const response = await apiClient.get('/admin/users');
      return response.data;
    }
  });

  const {  data: stats, isLoading: statsLoading } = useQuery<AdminStats>({
    queryKey: ['admin', 'stats'],
    queryFn: async () => {
      const response = await apiClient.get('/admin/stats');
      return response.data;
    }
  });

  const queryClient = useQueryClient();
  const { mutate: createUser, isPending: isCreating } = useMutation({
    mutationFn: async (userData: { username: string; password: string; role: string }) => {
      const response = await apiClient.post('/admin/users', userData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      setShowAddForm(false);
      setNewUsername('');
      setNewPassword('');
      setNewRole('user');
    }
  });

  const { mutate: deleteUser, isPending: isDeleting } = useMutation({
    mutationFn: async (userId: string) => {
      await apiClient.delete(`/admin/users/${userId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
    }
  });

  const { mutate: updateUserRole, isPending: isUpdating } = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      await apiClient.patch(`/admin/users/${userId}/role`, { role });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    }
  });

  const handleAddUser = (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (newUsername && newPassword) {
      createUser({ username: newUsername, password: newPassword, role: newRole });
    }
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}ч ${minutes}м`;
  };

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">👥 Панель администратора</h1>
        <Button variant="secondary" onClick={() => setShowAddForm(!showAddForm)}>
          {showAddForm ? '✕ Отмена' : '➕ Добавить пользователя'}
        </Button>
      </div>

      {/* Форма добавления пользователя */}
      {showAddForm && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Новый пользователь</h2>
          <form onSubmit={handleAddUser} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Имя пользователя
                </label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2"
                  placeholder="username"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Пароль
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2"
                  placeholder="••••••••"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Роль
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as 'user' | 'admin')}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2"
                >
                  <option value="user">Пользователь</option>
                  <option value="admin">Администратор</option>
                </select>
              </div>
            </div>
            <Button type="submit" isLoading={isCreating}>
              Создать пользователя
            </Button>
          </form>
        </Card>
      )}

      {/* Статистика */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary-100 rounded-lg">
              <span className="text-2xl">👥</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Всего пользователей</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? '...' : stats?.total_users || 0}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg">
              <span className="text-2xl">📄</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Всего транскрипций</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? '...' : stats?.total_transcripts || 0}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <span className="text-2xl">⏱️</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Общая длительность</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? '...' : formatDuration(stats?.total_duration || 0)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Таблица пользователей */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Пользователи</h2>
        
        {usersLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner text="Загрузка пользователей..." size={'sm'} />
          </div>
        ) : usersError ? (
          <ErrorMessage message="Не удалось загрузить пользователей" />
        ) : !users?.length ? (
          <p className="text-center text-gray-500 py-8">Нет пользователей</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left border-b">
                  <th className="pb-3 text-sm font-medium text-gray-500">ID</th>
                  <th className="pb-3 text-sm font-medium text-gray-500">Имя</th>
                  <th className="pb-3 text-sm font-medium text-gray-500">Email</th>
                  <th className="pb-3 text-sm font-medium text-gray-500">Роль</th>
                  <th className="pb-3 text-sm font-medium text-gray-500">Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.user_id} className="border-b hover:bg-gray-50">
                    <td className="py-3 text-sm text-gray-600 font-mono">
                      {user.user_id.slice(0, 8)}...
                    </td>
                    <td className="py-3 text-sm">
                      <div>
                        <p className="font-medium text-gray-900">{user.username}</p>
                        {user.full_name && (
                          <p className="text-gray-500 text-xs">{user.full_name}</p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 text-sm text-gray-600">{user.email || '—'}</td>
                    <td className="py-3">
                      <select
                        value={user.role}
                        onChange={(e) => updateUserRole({ 
                          userId: user.user_id, 
                          role: e.target.value 
                        })}
                        className="text-sm border border-gray-300 rounded px-2 py-1"
                        disabled={isUpdating}
                      >
                        <option value="user">Пользователь</option>
                        <option value="admin">Администратор</option>
                      </select>
                    </td>
                    <td className="py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700"
                        onClick={() => {
                          if (confirm('Удалить пользователя?')) {
                            deleteUser(user.user_id);
                          }
                        }}
                        disabled={isDeleting}
                      >
                        🗑️
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};