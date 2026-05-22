import apiClient from './client';
import type { ChatMessage, RAGResult } from '../types/transcript';

export const ragApi = {
  getChatHistory: async (transcriptId: string): Promise<ChatMessage[]> => {
    const response = await apiClient.get<{ messages: ChatMessage[] }>(`/chat/${transcriptId}`);
    return response.data.messages;
  },

  askQuestion: async (
    transcriptId: string,
    question: string,
    llmModel: string = 'deepseek/deepseek-v4-flash'
  ): Promise<{ answer: string }> => {
    const formData = new FormData();
    formData.append('transcript_id', transcriptId);
    formData.append('question', question);
    formData.append('llm_model', llmModel);

    const response = await apiClient.post<{ answer: string }>('/ask', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000
    });
    return response.data;
  },

  searchContext: async (
    query: string,
    excludeTranscriptId?: string,
    limit: number = 5
  ): Promise<RAGResult[]> => {
    const response = await apiClient.post<{ results: RAGResult[] }>('/rag/search', {
      query,
      exclude_transcript_id: excludeTranscriptId,
      limit
    });
    return response.data.results;
  }
};