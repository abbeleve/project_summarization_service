import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { crmApi, type SendTaskBody } from '@/api/crm';
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
    mutationFn: (body?: SendTaskBody) => crmApi.sendAllTasks(summaryId!, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-tasks', summaryId] });
    },
  });

  /** Отправить одну задачу в CRM. */
  const sendOneMutation = useMutation({
    mutationFn: (args: { taskId: string; body?: SendTaskBody }) =>
      crmApi.sendTask(args.taskId, args.body),
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

  /** Удалить задачу. */
  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => crmApi.deleteTask(taskId),
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
    deleteTask: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    refetch: tasksQuery.refetch,
  };
};

/** Хук: статус подключения CRM (есть ли у пользователя сохранённый API-токен Weeek). */
export const useCRMStatus = () => {
  return useQuery<{ connected: boolean }, Error>({
    queryKey: ['crm-status'],
    queryFn: crmApi.getStatus,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

/** Хук для списка проектов Weeek. Запрос уходит только при подключённой CRM. */
export const useCRMProjects = (enabled = true) => {
  return useQuery({
    queryKey: ['crm-projects'],
    queryFn: crmApi.getProjects,
    enabled,
    staleTime: 60_000,
  });
};

/** Хук для списка досок проекта Weeek. */
export const useCRMProjectBoards = (projectId: number | null) => {
  return useQuery({
    queryKey: ['crm-boards', projectId],
    queryFn: () => crmApi.getProjectBoards(projectId!),
    enabled: projectId != null,
    staleTime: 60_000,
  });
};

/** Хук для списка колонок доски Weeek. */
export const useCRMProjectBoardColumns = (boardId: number | null) => {
  return useQuery({
    queryKey: ['crm-columns', boardId],
    queryFn: () => crmApi.getBoardColumns(boardId!),
    enabled: boardId != null,
    staleTime: 60_000,
  });
};

/** Хук для списка участников workspace Weeek (назначаемых на задачи). */
export const useCRMWorskpaceMembers = (enabled = true) => {
  return useQuery({
    queryKey: ['crm-workspace-members'],
    queryFn: () => crmApi.getWorkspaceMembers(),
    enabled,
    staleTime: 120_000,
  });
};

export default useCRMTasks;
