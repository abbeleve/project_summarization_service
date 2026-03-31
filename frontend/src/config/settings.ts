import type { ProcessingSettings } from "@/types/transcript";

// export const API_URL = 'http://localhost:8000';

export const SUPPORTED_FORMATS = ['wav', 'mp3', 'm4a', 'flac', 'ogg', 'mp4'];

export const TRANSCRIBE_CONFIG: Record<string, string[]> = {
  gigaam: [
    'v3_ctc',
    'v3_rnnt',
    'v3_e2e_ctc',
    'v3_ssl'
  ],
  whisper: [
    'large-v3'
  ]
};

export const DIARIZATION_CONFIG: Record<string, string[]> = {
  pyannote: [
    'pyannote/speaker-diarization-community-1',
    'pyannote/speaker-diarization-community-2'
  ]
};

export const LLM_MODELS = [
  'arcee-ai/trinity-mini:free',
];

export const MEETING_TYPES = [
  'Оперативное совещание',
  'Стратегическое совещание',
  'Финансовое совещание',
  'HR-совещание',
  'Обзор проекта',
  'Экстренное совещание'
] as const;

export type MeetingType = typeof MEETING_TYPES[number];

export const DEFAULT_SETTINGS: ProcessingSettings = {
  transcribeModel: 'v3_ctc',
  diarizationModel: 'pyannote/speaker-diarization-community-1',
  diarizeLib: 'pyannote',
  transcribeLib: 'gigaam',
  llmModel: 'arcee-ai/trinity-mini:free',
  noiseSuppression: false
};

// export const API_TIMEOUTS = {
//   default: 30000,
//   processAudio: 300000, // 5 минут
//   summarize: 60000,
//   chat: 60000,
//   health: 5000
// };

// export const ROUTES = {
//   login: '/login',
//   home: '/',
//   analysis: '/analysis/:id',
//   admin: '/admin'
// } as const;

export function getTranscribeModelsByLib(libName: string): string[] {
  return TRANSCRIBE_CONFIG[libName] || [];
}

export function getDiarizationModelsByLib(libName: string): string[] {
  return DIARIZATION_CONFIG[libName] || [];
}

// export function getLibByTranscribeModel(modelName: string): string {
//   for (const [lib, models] of Object.entries(TRANSCRIBE_CONFIG)) {
//     if (models.includes(modelName)) return lib;
//   }
//   return 'gigaam';
// }

// export function getLibByDiarizationModel(modelName: string): string {
//   for (const [lib, models] of Object.entries(DIARIZATION_CONFIG)) {
//     if (models.includes(modelName)) return lib;
//   }
//   return 'pyannote';
// }