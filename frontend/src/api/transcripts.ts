import apiClient from './client';
import type { Transcript, ProcessAudioResponse, ProcessingSettings, TaskQueuedResponse } from '../types/transcript';

export interface TranscriptsResponse {
  items: Transcript[];
  total: number;
  limit: number;
  offset: number;
}

export interface SearchTranscriptsResponse extends TranscriptsResponse {
  query: string;
  search_type: string;
}

export const transcriptsApi = {
  processAudio: async (
    file: File,
    settings: ProcessingSettings
  ): Promise<ProcessAudioResponse | TaskQueuedResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('transcribe_model', settings.transcribeModel);
    formData.append('diarization_model', settings.diarizationModel);
    formData.append('diarize_lib', settings.diarizeLib);
    formData.append('transcribe_lib', settings.transcribeLib);
    formData.append('llm_model', settings.llmModel);
    formData.append('noise_sup_bool', settings.noiseSuppression.toString());

    const response = await apiClient.post<ProcessAudioResponse | TaskQueuedResponse>('/process', formData, {
      timeout: 300000
    });
    return response.data;
  },

  getAll: async (limit: number = 50, offset: number = 0): Promise<TranscriptsResponse> => {
    const response = await apiClient.get<TranscriptsResponse>(`/transcripts?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  search: async (
    query: string,
    searchType: string = 'exact',
    limit: number = 50,
    offset: number = 0
  ): Promise<SearchTranscriptsResponse> => {
    const response = await apiClient.get<SearchTranscriptsResponse>(
      `/transcripts/search?query=${encodeURIComponent(query)}&search_type=${searchType}&limit=${limit}&offset=${offset}`
    );
    return response.data;
  },

  getById: async (id: string): Promise<Transcript> => {
    const response = await apiClient.get<Transcript>(`/transcripts/${id}`);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/transcripts/${id}`);
  },

  applyNoiseSuppression: async (file: File): Promise<Blob> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/apply-noise-suppression', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob',
      timeout: 120000
    });
    return response.data;
  }
};