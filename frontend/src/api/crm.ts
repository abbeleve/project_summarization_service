import apiClient from './client';
import type { MeetingTask } from '@/types/transcript';

export interface CRMStatusResponse {
  connected: boolean;
}

export interface CRMConnectResponse {
  status: 'ok' | 'error';
  message: string;
}

export interface TaskSendResponse {
  status: 'ok' | 'error' | 'already_sent';
  message: string;
  crm_task_id?: string | null;
}

export interface WeeekProject {
  id: number;
  name: string;
  color?: string | null;
  is_private?: boolean | null;
}

export interface WeeekBoard {
  id: number;
  name: string;
  project_id: number;
  is_private?: boolean | null;
}

export interface WeeekBoardColumn {
  id: number;
  name: string;
  board_id: number;
}

export interface SendTaskBody {
  project_id?: number | null;
  board_column_id?: number | null;
  user_id?: string | null;
  deadline?: string | null;
}

export interface WeeekMember {
  id: string;
  name: string;
  email: string | null;
}

export const crmApi = {
  /** Проверка, подключена ли CRM интеграция у текущего пользователя. */
  getStatus: async (): Promise<CRMStatusResponse> => {
    const response = await apiClient.get<CRMStatusResponse>('/crm/connect/status');
    return response.data;
  },

  /** Сохранить API-токен Weeek. */
  connect: async (apiToken: string): Promise<CRMConnectResponse> => {
    const response = await apiClient.post<CRMConnectResponse>('/crm/connect', {
      api_token: apiToken,
    });
    return response.data;
  },

  /** Удалить API-токен Weeek. */
  disconnect: async (): Promise<CRMConnectResponse> => {
    const response = await apiClient.delete<CRMConnectResponse>('/crm/connect');
    return response.data;
  },

  /** Получить список MeetingTask для суммаризации. */
  getTasks: async (summaryId: string): Promise<MeetingTask[]> => {
    const response = await apiClient.get<MeetingTask[]>(`/crm/tasks/${summaryId}`);
    return response.data;
  },

  /** Отредактировать assignee/deadline задачи. */
  updateTask: async (
    taskId: string,
    body: { description?: string; assignee?: string; deadline?: string },
  ): Promise<MeetingTask> => {
    const response = await apiClient.patch<MeetingTask>(`/crm/tasks/${taskId}`, body);
    return response.data;
  },

  /** Получить список проектов из Weeek. */
  getProjects: async (): Promise<WeeekProject[]> => {
    const response = await apiClient.get<{ projects: WeeekProject[] }>('/crm/projects');
    return response.data.projects;
  },

  /** Получить список досок проекта. */
  getProjectBoards: async (projectId: number): Promise<WeeekBoard[]> => {
    const response = await apiClient.get<{ boards: WeeekBoard[] }>(`/crm/projects/${projectId}/boards`);
    return response.data.boards;
  },

  /** Получить список колонок доски. */
  getBoardColumns: async (boardId: number): Promise<WeeekBoardColumn[]> => {
    const response = await apiClient.get<{ board_columns: WeeekBoardColumn[] }>(`/crm/boards/${boardId}/columns`);
    return response.data.board_columns;
  },

  /** Получить список участников workspace из Weeek. */
  getWorkspaceMembers: async (): Promise<WeeekMember[]> => {
    const response = await apiClient.get<{ members: WeeekMember[] }>('/crm/workspace/members');
    return response.data.members;
  },

  /** Отправить одну задачу в CRM (с проектом и колонкой). */
  sendTask: async (taskId: string, body?: SendTaskBody): Promise<TaskSendResponse> => {
    const response = await apiClient.post<TaskSendResponse>(`/crm/tasks/${taskId}/send`, body ?? {});
    return response.data;
  },

  /** Отправить все неотправленные задачи в CRM (с проектом и колонкой). */
  sendAllTasks: async (
    summaryId: string,
    body?: SendTaskBody,
  ): Promise<{ status: string; sent: number; total: number; errors: unknown[] }> => {
    const response = await apiClient.post<{ status: string; sent: number; total: number; errors: unknown[] }>(
      `/crm/tasks/${summaryId}/send-all`,
      body ?? {},
    );
    return response.data;
  },

  /** Удалить задачу. Работает для отправленных и неотправленных. */
  deleteTask: async (taskId: string): Promise<void> => {
    await apiClient.delete(`/crm/tasks/${taskId}`);
  },
};

export default crmApi;
