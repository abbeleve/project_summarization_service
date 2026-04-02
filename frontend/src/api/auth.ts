import apiClient from './client';
import type { LoginCredentials, RegisterData, AuthResponse } from '../types/auth';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login', credentials);
    return response.data;
  },

  register: async (data: RegisterData): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/register', data);
    return response.data;
  },

  refreshAccessToken: async (refreshToken: string): Promise<{ access_token: string; token_type: string }> => {
    const response = await apiClient.post('/auth/refresh', { refresh_token: refreshToken });
    return response.data;
  },

//   getCurrentUser: async (): Promise<User> => {
//     const response = await apiClient.get<User>('/auth/me');
//     return response.data;
//   },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
};