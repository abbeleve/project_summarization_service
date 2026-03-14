export interface User {
  user_id: string;
  username: string;
  full_name: string;
  email?: string;
  role: 'user' | 'admin';
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  full_name: string;
}

export interface TokenPayload {
  sub: string;
  user_id: string;
  full_name?: string;
  role?: string;
  exp: number;
  type: 'access' | 'refresh';
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}