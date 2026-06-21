import apiClient from './client';

export interface CRMStatusResponse {
  connected: boolean;
}

export interface CRMConnectResponse {
  status: 'ok' | 'error';
  message: string;
}

export const crmApi = {
  getStatus: async (): Promise<CRMStatusResponse> => {
    const response = await apiClient.get<CRMStatusResponse>('/crm/connect/status');
    return response.data;
  },

  connect: async (apiToken: string): Promise<CRMConnectResponse> => {
    const response = await apiClient.post<CRMConnectResponse>('/crm/connect', {
      api_token: apiToken,
    });
    return response.data;
  },

  disconnect: async (): Promise<CRMConnectResponse> => {
    const response = await apiClient.delete<CRMConnectResponse>('/crm/connect');
    return response.data;
  },
};

export default crmApi;
