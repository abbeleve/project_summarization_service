import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { transcriptsApi } from '@/api/transcripts';
import type { Transcript, ProcessingSettings } from '@/types/transcript';

export const useTranscripts = () => {
  const queryClient = useQueryClient();

  const { data: transcripts, isLoading, error, refetch } = useQuery<Transcript[], Error>({
    queryKey: ['transcripts'],
    queryFn: transcriptsApi.getAll,
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
    transcripts,
    isLoading,
    error,
    refetch,
    processAudio: processMutation.mutateAsync,
    isProcessing: processMutation.isPending,
    deleteTranscript: deleteMutation.mutateAsync,
    getTranscript
  };
};