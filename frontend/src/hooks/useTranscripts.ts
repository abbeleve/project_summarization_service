import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { transcriptsApi, type TranscriptsResponse } from '@/api/transcripts';
import type { Transcript, ProcessingSettings, ProcessAudioResponse, TaskQueuedResponse } from '@/types/transcript';

interface UseTranscriptsOptions {
  limit?: number;
  offset?: number;
}

export const useTranscripts = (options: UseTranscriptsOptions = {}) => {
  const queryClient = useQueryClient();
  const { limit = 50, offset = 0 } = options;

  const { data: transcriptsData, isLoading, error, refetch } = useQuery<TranscriptsResponse, Error>({
    queryKey: ['transcripts', limit, offset],
    queryFn: () => transcriptsApi.getAll(limit, offset),
    staleTime: 5 * 60 * 1000,
    retry: 1
  });

  const processMutation = useMutation({
    mutationFn: ({ file, settings }: { file: File; settings: ProcessingSettings }) =>
      transcriptsApi.processAudio(file, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcripts'] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: transcriptsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transcripts'] });
    }
  });

  const getTranscript = (id: string) => {
    return useQuery<Transcript, Error>({
      queryKey: ['transcript', id],
      queryFn: () => transcriptsApi.getById(id),
      enabled: !!id,
      staleTime: 10 * 60 * 1000
    });
  };

  return {
    transcripts: transcriptsData?.items || [],
    total: transcriptsData?.total || 0,
    limit,
    offset,
    isLoading,
    error,
    refetch,
    processAudio: processMutation.mutateAsync as typeof processAudio,
    isProcessing: processMutation.isPending,
    deleteTranscript: deleteMutation.mutateAsync,
    getTranscript
  };
};

type processAudio = (data: { file: File; settings: ProcessingSettings }) => Promise<ProcessAudioResponse | TaskQueuedResponse>;