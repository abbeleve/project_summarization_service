import apiClient from './client';

export interface MeetingBotSettings {
  transcribe_model?: string;
  diarization_model?: string;
  diarize_lib?: string;
  transcribe_lib?: string;
  llm_model?: string;
  noise_suppression?: boolean;
}

export interface JoinMeetingPayload extends MeetingBotSettings {
  meeting_url: string;
  provider: 'google' | 'microsoft' | 'zoom';
  bot_name?: string;
}

export interface ScheduleMeetingPayload extends MeetingBotSettings {
  meeting_url: string;
  provider: 'google' | 'microsoft' | 'zoom';
  scheduled_at: string;
  bot_name?: string;
}

export interface ScheduledMeeting {
  id: string;
  user_id: string;
  meeting_url: string;
  provider: string;
  bot_name: string;
  scheduled_at: string;
  status: 'pending' | 'processing' | 'recording' | 'completed' | 'failed' | 'cancelled';
  meeting_bot_task_id: string | null;
  recording_url: string | null;
  result_transcript_id: string | null;
  transcribe_model: string;
  diarization_model: string;
  diarize_lib: string;
  transcribe_lib: string;
  llm_model: string;
  noise_suppression: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface JoinMeetingResponse {
  success: boolean;
  meeting_id: string;
  task_id: string;
  status: string;
  message: string;
}

export interface ScheduleMeetingResponse {
  success: boolean;
  meeting_id: string;
  status: string;
  scheduled_at: string;
  message: string;
}

export const meetingBotApi = {
  joinMeeting: (payload: JoinMeetingPayload) =>
    apiClient.post<JoinMeetingResponse>('/meetings/join', payload),

  scheduleMeeting: (payload: ScheduleMeetingPayload) =>
    apiClient.post<ScheduleMeetingResponse>('/meetings/schedule', payload),

  getMeetings: (limit = 50) =>
    apiClient.get<{ meetings: ScheduledMeeting[]; count: number }>('/meetings', { params: { limit } }),

  getMeeting: (id: string) =>
    apiClient.get<ScheduledMeeting>(`/meetings/${id}`),

  cancelMeeting: (id: string) =>
    apiClient.delete<{ success: boolean; meeting_id: string; status: string }>(`/meetings/${id}`),

  processNow: (id: string) =>
    apiClient.post<{ success: boolean; task_id: string; message: string }>(`/meetings/${id}/process-now`),
};

export default meetingBotApi;
