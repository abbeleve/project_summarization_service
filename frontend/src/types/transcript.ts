export interface TranscriptSegment {
  Speaker: string;
  Text: string;
  start: number;
  stop: number;
  avatarUrl?: string | null;
  colorSeed?: string | null;   // user_id для стабильного цвета
  dominantColor?: string | null; // hex-цвет из аватарки
}

export interface TranscriptPart {
  id: string;
  employee_id: string | null;
  transcript_id: string;
  text: string;
  start_time: number;
  end_time: number;
}

// export interface TranscriptSummary {
//   id: string;
//   transcript_id: string;
//   text: string;
//   key_points: string[];
//   meeting_type: string;
// }

export interface Transcript {
  transcript_id: string;
  title: string;
  original_text: string;
  created_at: string;
  summary: string | null;
  key_points: string[] | null;
  summary_id: string | null;
  meeting_type: string;
  parts: TranscriptPart[];
  segments?: TranscriptSegment[];
  speakers?: string[];
  duration?: number;
  audio_blob?: Blob;
  audio_url?: string;
  tasks?: TaskItem[] | null;
}

export interface TaskItem {
  description: string;
  assignee?: string;
  deadline?: string;
}

export interface MeetingTask {
  id: string;
  summary_id: string;
  description: string;
  assignee: string;
  deadline: string;
  sent_to_crm: boolean;
  sent_at: string | null;
  crm_task_id: string | null;
  created_at: string | null;
}

export interface TranscriptWithTasks extends Transcript {
  tasks?: TaskItem[] | null;
}

export interface ProcessingSettings {
  transcribeModel: string;
  diarizationModel: string;
  diarizeLib: string;
  transcribeLib: string;
  llmModel: string;
  noiseSuppression: boolean;
  meetingTitle?: string;
}

export interface ProcessAudioResponse {
  status: 'success';
  transcript_id: string;
  title: string;
  original_text: string;
  segments: TranscriptSegment[];
  summary: string;
  key_points: string[];
  meeting_type: string;
  speakers: string[];
  duration: number;
  parts: TranscriptPart[];
  used_models: {
    transcribe_model: string;
    diarization_model: string;
    transcribe_lib: string;
    diarize_lib: string;
  };
}

export interface TaskQueuedResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  poll_url: string;
  step?: string;
  progress?: number;
  result?: {
    transcript_id: string;
    title: string;
  };
  error?: string;
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface TaskInfo {
  task_id: string;
  status: TaskStatus;
  step?: string;
  progress?: number;
  error?: string;
  created_at?: string;
  updated_at?: string;
  result?: {
    transcript_id: string;
    title: string;
  };
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
}

export interface RAGResult {
  score: number;
  payload: {
    text: string;
    transcript_id: string;
    speaker: string;
    start_time: number;
    end_time: number;
    meeting_type: string;
    title: string;
  };
}