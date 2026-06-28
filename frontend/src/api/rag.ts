import apiClient from './client';
import type { ChatMessage, RAGResult, RAGSearchFilters } from '../types/transcript';

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
    limit: number = 5,
    filters?: RAGSearchFilters
  ): Promise<RAGResult[]> => {
    const body: Record<string, unknown> = {
      query,
      limit,
    };
    if (excludeTranscriptId) {
      body.exclude_transcript_id = excludeTranscriptId;
    }
    if (filters) {
      const cleanFilters: Record<string, string> = {};
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined && v !== null && v !== '') {
          cleanFilters[k] = v;
        }
      }
      if (Object.keys(cleanFilters).length > 0) {
        body.filters = cleanFilters;
      }
    }

    const response = await apiClient.post<{ results: RAGResult[] }>('/rag/search', body);
    return response.data.results;
  }
};
