import { useState } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { AppProvider } from '@/context/AppContext';
import { SidebarProvider } from '@/context/SidebarContext';
import { Header } from '@/components/ui/Sidebar';
import { TranscriptionHistoryPanel } from '@/components/transcriptions/TranscriptionHistoryPanel';
import { RightPanel } from '@/components/transcriptions/RightPanel';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { HomePage } from '@/pages/HomePage';
import { NewAnalysisPage } from '@/pages/NewAnalysisPage';
import { AnalysisPage } from '@/pages/AnalysisPage';
import { AdminPage } from '@/pages/AdminPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { SettingsPage } from '@/pages/SettingsPage';
import MeetingBotPage from '@/pages/MeetingBotPage';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner text="Проверка авторизации..." size={'sm'} />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner text="Проверка прав..." size={'sm'} />
      </div>
    );
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const isHomePage = location.pathname === '/';
  const showRightPanel = isHomePage || location.pathname === '/meeting-bot' || location.pathname === '/new-analysis';
  const [rightPanelOpen, setRightPanelOpen] = useState(true);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-100 via-gray-50 to-gray-100 dark:from-dark-base-900 dark:via-dark-base-800 dark:to-dark-base-900 transition-colors duration-300">
      <Header />
      <div className="flex flex-nowrap relative">
        <TranscriptionHistoryPanel />
        <div className="flex-1 flex justify-center min-w-0 max-w-full">
          <main className="w-full max-w-[1600px] bg-white dark:bg-dark-base-900 min-h-screen shadow-2xl">
            <div className="p-6">
              {children}
            </div>
          </main>
        </div>
        {showRightPanel && rightPanelOpen && <RightPanel />}
      </div>

      {/* Toggle button for right panel */}
      {showRightPanel && (
        <button
          onClick={() => setRightPanelOpen(v => !v)}
          className="fixed top-1/2 -translate-y-1/2 z-50 w-7 h-12 rounded-l-lg bg-white dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 border-r-0 flex items-center justify-center shadow-md hover:shadow-lg hover:bg-gray-50 dark:hover:bg-dark-base-700 transition-all cursor-pointer text-xs text-gray-400 dark:text-gray-500"
          style={{ right: rightPanelOpen ? '320px' : '0' }}
          title={rightPanelOpen ? 'Скрыть панель' : 'Показать панель'}
        >
          {rightPanelOpen ? '▶' : '◀'}
        </button>
      )}

      {/* Floating button — Новый анализ (только на главной) */}
      {isHomePage && (
        <button
          onClick={() => navigate('/new-analysis')}
          className="fixed bottom-6 z-50 max-w-4xl w-[calc(100vw-24rem)] flex items-center justify-center px-6 py-4 rounded-2xl bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold text-xl shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] transition-all duration-200"
          style={{ left: 'calc(50vw + 10px)', transform: 'translateX(-50%)' }}
        >
          Новый анализ
        </button>
      )}
    </div>
  );
};

function AppContent() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route path="/" element={
        <ProtectedRoute>
          <AppLayout>
            <HomePage />
          </AppLayout>
        </ProtectedRoute>
      } />

      <Route path="/new-analysis" element={
        <ProtectedRoute>
          <AppLayout>
            <NewAnalysisPage />
          </AppLayout>
        </ProtectedRoute>
      } />

      <Route path="/analysis/:id" element={
        <ProtectedRoute>
          <AppLayout>
            <AnalysisPage />
          </AppLayout>
        </ProtectedRoute>
      } />
      
      <Route path="/admin" element={
        <AdminRoute>
          <AppLayout>
            <AdminPage />
          </AppLayout>
        </AdminRoute>
      } />

      <Route path="/meeting-bot" element={
        <ProtectedRoute>
          <AppLayout>
            <MeetingBotPage />
          </AppLayout>
        </ProtectedRoute>
      } />

      <Route path="/profile" element={
        <ProtectedRoute>
          <AppLayout>
            <ProfilePage />
          </AppLayout>
        </ProtectedRoute>
      } />

      <Route path="/settings" element={
        <ProtectedRoute>
          <AppLayout>
            <SettingsPage />
          </AppLayout>
        </ProtectedRoute>
      } />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppProvider>
          <SidebarProvider>
            <AppContent />
          </SidebarProvider>
        </AppProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}