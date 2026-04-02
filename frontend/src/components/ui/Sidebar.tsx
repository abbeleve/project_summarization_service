import { NavLink, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/context/ThemeContext';
import { clsx } from 'clsx';

interface NavItem {
  label: string;
  icon: string;
  path: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Главная', icon: '🏠', path: '/' },
  { label: 'Пользователи', icon: '👥', path: '/admin', adminOnly: true },
];

export const Header = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const visibleItems = NAV_ITEMS.filter(item =>
    !item.adminOnly || user?.role === 'admin'
  );

  return (
    <header className="bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-md sticky top-0 z-50 border-b border-gray-200 dark:border-gray-700 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Логотип */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
              <span className="text-2xl">🎙️</span>
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-bold text-gray-900 dark:text-white leading-tight">Meeting Insight</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">Анализ встреч</p>
            </div>
          </div>

          {/* Правая часть - профиль и переключатель */}
          <div className="flex items-center gap-3">
            {/* Переключатель темы */}
            <button
              onClick={() => {
                console.log('Toggle theme, current:', theme);
                toggleTheme();
              }}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
              title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
              type="button"
            >
              <span className="text-xl">
                {theme === 'dark' ? '☀️' : '🌙'}
              </span>
            </button>

            {/* Инфо о пользователе */}
            <div className="hidden md:flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center shadow-md">
                <span className="text-sm font-bold text-white">
                  {user?.full_name?.charAt(0).toUpperCase() || 'U'}
                </span>
              </div>
              <div className="flex flex-col">
                <p className="text-sm font-semibold text-gray-900 dark:text-white whitespace-nowrap">
                  {user?.full_name || 'Пользователь'}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {user?.role === 'admin' && (
                    <span className="px-1.5 py-0.5 bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 rounded text-xs">
                      Админ
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* Кнопка выхода */}
            <button
              onClick={() => {
                logout(() => queryClient.clear());
                navigate('/login');
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 border border-red-200 dark:border-red-800 transition-all"
              title="Выйти"
            >
              <span className="text-lg">🚪</span>
              <span className="font-medium hidden sm:inline">Выйти</span>
            </button>
          </div>

          {/* Центр - Навигация */}
          <nav className="flex items-center gap-1">
            {visibleItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg transition-all',
                    isActive
                      ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 shadow-md'
                      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white'
                  )
                }
              >
                <span className="text-xl">{item.icon}</span>
                <span className="font-medium hidden sm:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
};

// Оставляем Sidebar для обратной совместимости, но не используем
export const Sidebar = Header;