import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { transcriptsApi, type Annotation } from '@/api/transcripts';

export const useAnnotations = (transcriptId: string) => {
  const queryClient = useQueryClient();

  const { data: annotations, isLoading, error } = useQuery<Annotation[], Error>({
    queryKey: ['annotations', transcriptId],
    queryFn: () => transcriptsApi.getAnnotations(transcriptId),
    enabled: !!transcriptId,
    staleTime: 5 * 60 * 1000
  });

  const createMutation = useMutation({
    mutationFn: (data: { part_id: string; start_char: number; end_char: number; color?: string; note?: string }) =>
      transcriptsApi.createAnnotation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['annotations', transcriptId] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: transcriptsApi.deleteAnnotation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['annotations', transcriptId] });
    }
  });

  return {
    annotations: annotations || [],
    isLoading,
    error,
    createAnnotation: createMutation.mutateAsync,
    deleteAnnotation: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isDeleting: deleteMutation.isPending
  };
};
