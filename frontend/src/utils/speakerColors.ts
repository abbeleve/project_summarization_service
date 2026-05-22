// Генерация последовательного цвета для спикера
// Использует hash от имени спикера для консистентности
const SPEAKER_COLORS = [
  { bg: 'bg-blue-500', light: 'bg-blue-100', text: 'text-blue-700' },
  { bg: 'bg-green-500', light: 'bg-green-100', text: 'text-green-700' },
  { bg: 'bg-orange-500', light: 'bg-orange-100', text: 'text-orange-700' },
  { bg: 'bg-blue-500', light: 'bg-blue-100', text: 'text-blue-700' },
  { bg: 'bg-pink-500', light: 'bg-pink-100', text: 'text-pink-700' },
  { bg: 'bg-indigo-500', light: 'bg-indigo-100', text: 'text-indigo-700' },
  { bg: 'bg-red-500', light: 'bg-red-100', text: 'text-red-700' },
  { bg: 'bg-yellow-500', light: 'bg-yellow-100', text: 'text-yellow-700' },
  { bg: 'bg-teal-500', light: 'bg-teal-100', text: 'text-teal-700' },
  { bg: 'bg-cyan-500', light: 'bg-cyan-100', text: 'text-cyan-700' },
  { bg: 'bg-rose-500', light: 'bg-rose-100', text: 'text-rose-700' },
  { bg: 'bg-blue-500', light: 'bg-blue-100', text: 'text-blue-700' },
  { bg: 'bg-lime-500', light: 'bg-lime-100', text: 'text-lime-700' },
  { bg: 'bg-amber-500', light: 'bg-amber-100', text: 'text-amber-700' },
  { bg: 'bg-emerald-500', light: 'bg-emerald-100', text: 'text-emerald-700' },
  { bg: 'bg-sky-500', light: 'bg-sky-100', text: 'text-sky-700' },
];

export const getSpeakerColor = (speaker: string) => {
  // Создаём хеш из имени спикера для консистентного цвета
  let hash = 0;
  for (let i = 0; i < speaker.length; i++) {
    hash = speaker.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % SPEAKER_COLORS.length;
  return SPEAKER_COLORS[index];
};

/** Версия getSpeakerColor, принимающая user_id как seed.
 *  Используется для идентифицированных спикеров — цвет закрепляется за аккаунтом,
 *  а не за строкой-именем. */
export const getSpeakerColorBySeed = (seed: string) => {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % SPEAKER_COLORS.length;
  return SPEAKER_COLORS[index];
};
