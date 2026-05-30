import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { voiceApi, usersApi } from '@/api/voice';
import { VoiceRecorder } from '@/components/voice/VoiceRecorder';
import type { UserProfile, VoiceProfile } from '@/types/voice';
import { Card } from '@/components/ui/Card';
import { clsx } from 'clsx';

export const ProfilePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // User profile state
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ surname: '', name: '', patronymic: '', email: '' });
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Avatar state
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarDeleting, setAvatarDeleting] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  // Voice profile state
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null);
  const [voiceLoading, setVoiceLoading] = useState(true);
  const [deletingVoice, setDeletingVoice] = useState(false);

  const fetchProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      const data = await usersApi.getProfile();
      setProfile(data);
      setEditForm({
        surname: data.surname || '',
        name: data.name || '',
        patronymic: data.patronymic || '',
        email: data.email || '',
      });
    } catch {
      setProfileError('Не удалось загрузить профиль');
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const fetchVoiceProfile = useCallback(async () => {
    setVoiceLoading(true);
    try {
      const data = await voiceApi.getProfile();
      setVoiceProfile(data);
    } catch {
      // Non-critical
    } finally {
      setVoiceLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
    fetchVoiceProfile();
  }, [fetchProfile, fetchVoiceProfile]);

  const handleRefreshVoice = useCallback(() => {
    fetchVoiceProfile();
  }, [fetchVoiceProfile]);

  const handleSaveProfile = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      const updated = await usersApi.updateProfile(editForm);
      setProfile(updated);
      setEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Ошибка сохранения';
      setProfileError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteVoice = async () => {
    if (!confirm('Удалить голосовой профиль? Это отключит идентификацию вас как спикера.')) return;
    setDeletingVoice(true);
    try {
      await voiceApi.deleteProfile();
      setVoiceProfile({ has_profile: false, created_at: null });
    } catch {
      // ignore
    } finally {
      setDeletingVoice(false);
    }
  };

  const handleCancelEdit = () => {
    setEditing(false);
    if (profile) {
      setEditForm({
        surname: profile.surname,
        name: profile.name,
        patronymic: profile.patronymic,
        email: profile.email,
      });
    }
  };

  const handleAvatarSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAvatarUploading(true);
    setAvatarError(null);
    try {
      await usersApi.uploadAvatar(file);
      // Refresh profile to get updated avatar_url
      const updated = await usersApi.getProfile();
      setProfile(updated);
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : 'Ошибка загрузки');
    } finally {
      setAvatarUploading(false);
      // Reset file input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteAvatar = async () => {
    if (!confirm('Удалить фото профиля?')) return;
    setAvatarDeleting(true);
    setAvatarError(null);
    try {
      await usersApi.deleteAvatar();
      const updated = await usersApi.getProfile();
      setProfile(updated);
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : 'Ошибка удаления');
    } finally {
      setAvatarDeleting(false);
    }
  };

  if (!user) {
    navigate('/login');
    return null;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Личный кабинет</h1>

      {/* Profile info card */}
      <Card>
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Информация о пользователе</h2>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
              >
                ✏️ Редактировать
              </button>
            )}
          </div>

          {profileLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Загрузка...
            </div>
          ) : profileError ? (
            <p className="text-red-500 text-sm">{profileError}</p>
          ) : profile ? (
            <div className="space-y-4">
              {/* Avatar + basic info */}
              <div className="flex items-center gap-4">
                <div className="relative group">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center shadow-lg overflow-hidden">
                    {profile.avatar_url ? (
                      <img
                        src={profile.avatar_url}
                        alt="Avatar"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-2xl font-bold text-white">
                        {(profile.surname?.[0] || '').toUpperCase()}
                      </span>
                    )}
                  </div>
                  {/* Upload overlay */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={avatarUploading}
                    className="absolute inset-0 w-full h-full rounded-full bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-medium cursor-pointer"
                    title="Сменить фото"
                  >
                    {avatarUploading ? (
                      <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      '📷'
                    )}
                  </button>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleAvatarSelect}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-lg font-semibold text-gray-900 dark:text-white">
                      {editing ? (
                        <span className="text-sm font-normal text-gray-500">Редактирование</span>
                      ) : (
                        `${profile.surname} ${profile.name} ${profile.patronymic || ''}`.trim()
                      )}
                    </p>
                    {profile.avatar_url && !editing && (
                      <button
                        onClick={handleDeleteAvatar}
                        disabled={avatarDeleting}
                        className="text-xs text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
                        title="Удалить фото"
                      >
                        {avatarDeleting ? '...' : '✕'}
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">@{profile.username}</p>
                </div>
              </div>

              {avatarError && (
                <p className="text-sm text-red-500">{avatarError}</p>
              )}

              {/* Edit form */}
              {editing ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Фамилия</label>
                    <input
                      type="text"
                      value={editForm.surname}
                      onChange={(e) => setEditForm(p => ({ ...p, surname: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Имя</label>
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm(p => ({ ...p, name: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Отчество</label>
                    <input
                      type="text"
                      value={editForm.patronymic}
                      onChange={(e) => setEditForm(p => ({ ...p, patronymic: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
                    <input
                      type="email"
                      value={editForm.email}
                      onChange={(e) => setEditForm(p => ({ ...p, email: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-dark-base-600 rounded-lg bg-white dark:bg-dark-base-800 text-gray-900 dark:text-white text-sm"
                    />
                  </div>
                  <div className="sm:col-span-2 flex gap-2 pt-2">
                    <button
                      onClick={handleSaveProfile}
                      disabled={saving}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-lg transition-colors flex items-center gap-2"
                    >
                      {saving && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                      Сохранить
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-dark-base-700 hover:bg-gray-200 dark:hover:bg-dark-base-600 rounded-lg transition-colors"
                    >
                      Отмена
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Email:</span>
                    <span className="ml-2 text-gray-900 dark:text-white">{profile.email}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Логин:</span>
                    <span className="ml-2 text-gray-900 dark:text-white">{profile.username}</span>
                  </div>
                </div>
              )}

              {saveSuccess && (
                <p className="text-sm text-emerald-600 dark:text-emerald-400">✓ Профиль обновлён</p>
              )}
            </div>
          ) : null}
        </div>
      </Card>

      {/* Voice profile card */}
      <Card>
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Голосовой профиль</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Запишите свой голос для идентификации вас как спикера в расшифровках встреч
              </p>
            </div>
            {voiceProfile?.has_profile && !voiceLoading && (
              <button
                onClick={handleDeleteVoice}
                disabled={deletingVoice}
                className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium flex items-center gap-1"
              >
                {deletingVoice ? 'Удаление...' : '🗑 Удалить'}
              </button>
            )}
          </div>

          {voiceLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Загрузка...
            </div>
          ) : (
            <VoiceRecorder
              hasExistingProfile={voiceProfile?.has_profile || false}
              onProfileChange={handleRefreshVoice}
            />
          )}
        </div>
      </Card>

      {/* How it works */}
      <Card>
        <div className="p-6">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Как это работает</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="text-center p-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-2">
                <span className="text-lg">🎤</span>
              </div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">1. Запись голоса</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Запишите 10–30 секунд речи</p>
            </div>
            <div className="text-center p-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-2">
                <span className="text-lg">🧬</span>
              </div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">2. Создание эмбеддинга</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Нейросеть создаёт уникальный вектор голоса</p>
            </div>
            <div className="text-center p-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-2">
                <span className="text-lg">🔍</span>
              </div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">3. Идентификация</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Система узнаёт вас в новых встречах</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};