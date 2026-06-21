import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { crmApi } from '@/api/crm';
import type { MeetingTask } from '@/types/transcript';

export const useCRMTasks = (summaryId: string | null) => {
  const queryClient = useQueryClient();

  const tasksQuery = useQuery<MeetingTask[], Error>({
    queryKey: ['crm-tasks', summaryId],
    queryFn: () => crmApi.getTasks(summaryId!),
    enabled: !!summaryId,
    staleTime: 30_000,
  });

  /** Отправить все неотправленные задачи в CRM. */
  const sendAllMutation = useMutation({
    mutationFn: () => crmApi.sendAllTasks(summaryId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-tasks', summaryId] });
    },
  });

  /** Отправить одну задачу в CRM. */
  const sendOneMutation = useMutation({
    mutationFn: (taskId: string) => crmApi.sendTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-tasks', summaryId] });
    },
  });

  /** Обновить description / assignee / deadline задачи. */
  const updateMutation = useMutation({
    mutationFn: (args: { taskId: string; description?: string; assignee?: string; deadline?: string }) =>
      crmApi.updateTask(args.taskId, { description: args.description, assignee: args.assignee, deadline: args.deadline }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-tasks', summaryId] });
    },
  });

  return {
    tasks: tasksQuery.data ?? [],
    isLoading: tasksQuery.isLoading,
    isSendAllPending: sendAllMutation.isPending,
    sendAllToCRM: sendAllMutation.mutate,
    sendAllResult: sendAllMutation.data,
    sendOneToCRM: sendOneMutation.mutate,
    isSendingOne: sendOneMutation.isPending,
    updateTask: updateMutation.mutate,
    refetch: tasksQuery.refetch,
  };
};

export default useCRMTasks;
