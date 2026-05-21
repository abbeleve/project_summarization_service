import apiClient from './client';
import type { VoiceProfile, EnrolledSpeakers, UserProfile, UpdateProfileData } from '@/types/voice';

export const voiceApi = {
  /** Enroll voice: upload audio file to create/update voice profile */
  enroll: async (audioBlob: Blob): Promise<VoiceProfile> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'voice_recording.wav');
    const response = await apiClient.post<VoiceProfile>('/voice/enroll', formData);
    return response.data;
  },

  /** Get current user's voice profile status */
  getProfile: async (): Promise<VoiceProfile> => {
    const response = await apiClient.get<VoiceProfile>('/voice/profile');
    return response.data;
  },

  /** Delete current user's voice profile */
  deleteProfile: async (): Promise<void> => {
    await apiClient.delete('/voice/profile');
  },

  /** List all enrolled speakers */
  getEnrolledSpeakers: async (): Promise<EnrolledSpeakers> => {
    const response = await apiClient.get<EnrolledSpeakers>('/voice/enrolled-speakers');
    return response.data;
  },

  /** Get voice enrollment stats */
  getStats: async (): Promise<{ enrolled_count: number }> => {
    const response = await apiClient.get('/voice/stats');
    return response.data;
  },
};

export const usersApi = {
  /** Get current user's full profile */
  getProfile: async (): Promise<UserProfile> => {
    const response = await apiClient.get<UserProfile>('/users/me');
    return response.data;
  },

  /** Update current user's profile */
  updateProfile: async (data: UpdateProfileData): Promise<UserProfile> => {
    const response = await apiClient.put<UserProfile>('/users/me', data);
    return response.data;
  },

  /** Upload avatar image */
  uploadAvatar: async (file: File): Promise<{ avatar_url: string; message: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/users/me/avatar', formData);
    return response.data;
  },

  /** Delete avatar */
  deleteAvatar: async (): Promise<{ message: string }> => {
    const response = await apiClient.delete('/users/me/avatar');
    return response.data;
  },
};