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

  /** Отправить одну задачу в CRM (mock — помечает sent). */
  sendTask: async (taskId: string): Promise<TaskSendResponse> => {
    const response = await apiClient.post<TaskSendResponse>(`/crm/tasks/${taskId}/send`);
    return response.data;
  },

  /** Отправить все неотправленные задачи в CRM. */
  sendAllTasks: async (summaryId: string): Promise<{ status: string; sent: number; total: number; errors: unknown[] }> => {
    const response = await apiClient.post<{ status: string; sent: number; total: number; errors: unknown[] }>(
      `/crm/tasks/${summaryId}/send-all`,
    );
    return response.data;
  },
};

export default crmApi;
