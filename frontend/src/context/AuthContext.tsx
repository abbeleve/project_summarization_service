import { createContext, useContext, useState, useEffect, type ReactNode, useCallback } from 'react';
import { jwtDecode } from 'jwt-decode';
import { authApi } from '@/api/auth';
import type { User, AuthState, LoginCredentials, RegisterData, TokenPayload } from '@/types/auth';

interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: (clearCache?: () => void) => void;
  refreshAccessToken: () => Promise<boolean>;
  isTokenExpired: (token: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true,
    error: null
  });

  const isTokenExpired = useCallback((token: string): boolean => {
    try {
      const { exp } = jwtDecode<TokenPayload>(token);
      return Date.now() >= (exp - 60) * 1000;
    } catch {
      return true;
    }
  }, []);

  const checkAuth = useCallback(async () => {
    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (accessToken && !isTokenExpired(accessToken)) {
      try {
        const payload = jwtDecode<TokenPayload>(accessToken);
        const user: User = {
          user_id: payload.user_id,
          username: payload.sub,
          full_name: payload.full_name || '',
          email: '',
          role: payload.role === 'admin' ? 'admin' : 'user'
        };
        
        setState({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
          isLoading: false,
          error: null
        });
        return;
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
    }
    
    setState(prev => ({ ...prev, isLoading: false }));
  }, [isTokenExpired]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (credentials: LoginCredentials) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await authApi.login(credentials);

      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);

      const payload = jwtDecode<TokenPayload>(response.access_token);
      const user: User = {
        user_id: response.user_id,
        username: credentials.username,
        full_name: response.full_name,
        email: '',
        role: payload.role === 'admin' ? 'admin' : 'user'
      };

      setState({
        user,
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Ошибка авторизации';
      setState(prev => ({ ...prev, isLoading: false, error: message }));
      throw error;
    }
  };

  const register = async (data: RegisterData) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await authApi.register(data);

      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);

      const payload = jwtDecode<TokenPayload>(response.access_token);
      const user: User = {
        user_id: response.user_id,
        username: data.username,
        full_name: `${data.surname} ${data.name}`,
        email: data.email,
        role: payload.role === 'admin' ? 'admin' : 'user'
      };

      setState({
        user,
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Ошибка регистрации';
      setState(prev => ({ ...prev, isLoading: false, error: message }));
      throw error;
    }
  };

  const logout = useCallback((clearCache?: () => void) => {
    authApi.logout();
    clearCache?.();
    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null
    });
  }, []);

  const refreshAccessToken = useCallback(async (): Promise<boolean> => {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) return false;
    
    try {
      const response = await authApi.refreshAccessToken(refresh);
      localStorage.setItem('access_token', response.access_token);
      
      setState(prev => ({
        ...prev,
        accessToken: response.access_token,
        error: null
      }));
      return true;
    } catch {
      logout();
      return false;
    }
  }, [logout]);

  return (
    <AuthContext.Provider value={{
      ...state,
      login,
      register,
      logout,
      refreshAccessToken,
      isTokenExpired
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth нужно использовать внутри AuthProvider');
  }
  return context;
};