export interface ApiError {
  detail: string;
  status_code?: number;
}

// export interface HealthCheckResponse {
//   status: 'healthy' | 'degraded';
//   service: string;
//   database: string;
//   timestamp: string;
// }

// export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

// export interface ApiRequestOptions {
//   method: HttpMethod;
//   endpoint: string;
//   data?: unknown;
//   formData?: FormData;
//   headers?: Record<string, string>;
//   timeout?: number;
//   requireAuth?: boolean;
// }