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

/** Описания моделей транскрипции для тултипов */
export const TRANSCRIBE_MODEL_DESCRIPTIONS: Record<string, {
  library: string;
  description: string;
  language: string;
  speed: string;
  size: string;
}> = {
  gigaam: {
    library: 'gigaam',
    description: 'Отечественная модель от Сбера. Отлично работает с русским языком.',
    language: '🇷🇺 Русский (основной)',
    speed: ' Быстрая',
    size: ' Лёгкая'
  },
  whisper: {
    library: 'whisper',
    description: 'Модель от OpenAI. Отлично работает с иностранными языками.',
    language: '🌍 Мультиязычная (EN, DE, FR, ES и др.)',
    speed: '🐢 Медленнее gigaAM',
    size: '🏋️ Тяжёлая (требует больше ресурсов)'
  }
};

/** Описания моделей диаризации для тултипов */
export const DIARIZATION_MODEL_DESCRIPTIONS: Record<string, {
  library: string;
  description: string;
  accuracy: string;
  speed: string;
}> = {
  'pyannote/speaker-diarization-community-1': {
    library: 'pyannote',
    description: 'Популярная модель для определения спикеров. Хороший баланс качества и скорости.',
    accuracy: '⭐⭐⭐⭐ Высокое',
    speed: '🚀 Средняя скорость'
  },
  'pyannote/speaker-diarization-community-2': {
    library: 'pyannote',
    description: 'Улучшенная версия с повышенной точностью определения спикеров.',
    accuracy: '⭐⭐⭐⭐⭐ Очень высокое',
    speed: '🐢 Немного медленнее'
  }
};

/** Описания LLM моделей для тултипов */
export const LLM_MODEL_DESCRIPTIONS: Record<string, {
  description: string;
  speed: string;
  context: string;
}> = {
  'deepseek/deepseek-v4-flash': {
    description: 'Быстрая и эффективная модель от DeepSeek для суммаризации.',
    speed: '🚀 Очень быстрая',
    context: '📚 Большой контекст'
  }
};

export const DIARIZATION_CONFIG: Record<string, string[]> = {
  pyannote: [
    'pyannote/speaker-diarization-community-1',
    'pyannote/speaker-diarization-community-2'
  ]
};

export const LLM_MODELS = [
  'deepseek/deepseek-v4-flash',
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
  llmModel: 'deepseek/deepseek-v4-flash',
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