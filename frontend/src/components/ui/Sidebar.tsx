import { useState, useRef, useEffect } from 'react';
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
  { label: 'Meeting Bot', icon: '🤖', path: '/meeting-bot' },
  { label: 'Пользователи', icon: '👥', path: '/admin', adminOnly: true },
];

export const Header = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const visibleItems = NAV_ITEMS.filter(item =>
    !item.adminOnly || user?.role === 'admin'
  );

  const handleLogout = () => {
    logout(() => queryClient.clear());
    navigate('/login');
  };

  return (
    <header className="bg-white dark:bg-dark-base-900 text-gray-900 dark:text-white shadow-md sticky top-0 z-50 border-b border-gray-200 dark:border-dark-base-700 transition-colors">
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
                      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-800 hover:text-gray-900 dark:hover:text-white'
                  )
                }
              >
                <span className="text-xl">{item.icon}</span>
                <span className="font-medium hidden sm:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>

          {/* Правая часть - профиль с выпадающим меню */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 hover:bg-gray-200 dark:hover:bg-dark-base-700 transition-all cursor-pointer"
              type="button"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center shadow-md overflow-hidden">
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt="Avatar"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-sm font-bold text-white">
                    {user?.full_name?.charAt(0).toUpperCase() || 'U'}
                  </span>
                )}
              </div>
              <div className="hidden sm:flex flex-col text-left">
                <p className="text-sm font-semibold text-gray-900 dark:text-white whitespace-nowrap leading-tight">
                  {user?.full_name || 'Пользователь'}
                </p>
              </div>
              <svg
                className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Выпадающее меню */}
            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 rounded-xl shadow-xl py-2 z-50">
                {/* Имя пользователя и роль в шапке меню */}
                <div className="px-4 py-2 border-b border-gray-100 dark:border-dark-base-700">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">{user?.full_name || 'Пользователь'}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {user?.role === 'admin' ? 'Администратор' : 'Пользователь'}
                  </p>
                </div>

                {/* Переключатель темы */}
                <button
                  onClick={() => {
                    toggleTheme();
                    setDropdownOpen(false);
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-base-700 transition-colors"
                  type="button"
                >
                  <span className="text-lg">{theme === 'dark' ? '☀️' : '🌙'}</span>
                  <span>{theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}</span>
                </button>

                {/* Профиль */}
                <NavLink
                  to="/profile"
                  onClick={() => setDropdownOpen(false)}
                  className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-base-700 transition-colors"
                >
                  <span className="text-lg">👤</span>
                  <span>Профиль</span>
                </NavLink>

                {/* Разделитель */}
                <div className="border-t border-gray-100 dark:border-dark-base-700 my-1" />

                {/* Выйти */}
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    handleLogout();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  type="button"
                >
                  <span className="text-lg">🚪</span>
                  <span>Выйти</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

// Оставляем Sidebar для обратной совместимости, но не используем
export const Sidebar = Header;