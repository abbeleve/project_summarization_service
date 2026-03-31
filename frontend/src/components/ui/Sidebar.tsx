import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { clsx } from 'clsx';

interface NavItem {
  label: string;
  icon: string;
  path: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Главная', icon: '🏠', path: '/' },
  { label: 'Анализ', icon: '📊', path: '/analysis', adminOnly: false },
  { label: 'Пользователи', icon: '👥', path: '/admin', adminOnly: true },
];

export const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const visibleItems = NAV_ITEMS.filter(item => 
    !item.adminOnly || user?.role === 'admin'
  );

  return (
    <aside className="w-64 bg-gray-900 text-white min-h-screen p-4 relative">
      <div className="flex items-center gap-3 px-4 py-4 mb-6 border-b border-gray-700">
        <span className="text-3xl">🎙️</span>
        <div>
          <h1 className="text-lg font-bold text-white">Meeting Insight</h1>
          <p className="text-xs text-gray-400">Анализ встреч</p>
        </div>
      </div>
      <nav className="space-y-2">
        {visibleItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <span className="text-xl">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-6 pt-6 border-t border-gray-700">
        <div className="flex items-center gap-3 px-4 py-3 mb-2">
          <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center">
            <span className="text-sm font-bold">
              {user?.full_name?.charAt(0) || 'U'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">
              {user?.full_name || 'Пользователь'}
            </p>
            {/* <p className="text-xs text-gray-400 truncate">
              {user?.username || ''}
            </p> */}
          </div>
        </div>
        <button
          onClick={() => {
            logout();
            navigate('/login');
          }}
          className="w-full flex items-center gap-3 px-4 py-3 text-gray-300 hover:bg-gray-800 hover:text-white rounded-lg transition-colors"
        >
          <span className="text-xl">🚪</span>
          <span className="font-medium">Выйти</span>
        </button>
      </div>
    </aside>
  );
};