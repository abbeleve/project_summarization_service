/**
 * Палитра для участников Weeek (назначаются на CRM-задачи).
 *
 * Эта палитра НЕ пересекается со speakerColors — спикеры диаризации и
 * участники проекта Weeek живут в разных доменах. Цвет юзера Weeek
 * детерминируется по его `id`, чтобы он не менялся между рендерами.
 */
const WEEEK_MEMBER_PALETTE = [
  { ring: 'ring-violet-500',   bg: 'bg-violet-100 dark:bg-violet-500/15',   text: 'text-violet-700 dark:text-violet-300' },
  { ring: 'ring-cyan-500',     bg: 'bg-cyan-100 dark:bg-cyan-500/15',       text: 'text-cyan-700 dark:text-cyan-300' },
  { ring: 'ring-sky-500',      bg: 'bg-sky-100 dark:bg-sky-500/15',         text: 'text-sky-700 dark:text-sky-300' },
  { ring: 'ring-emerald-500',  bg: 'bg-emerald-100 dark:bg-emerald-500/15', text: 'text-emerald-700 dark:text-emerald-300' },
  { ring: 'ring-amber-500',    bg: 'bg-amber-100 dark:bg-amber-500/15',     text: 'text-amber-700 dark:text-amber-300' },
  { ring: 'ring-rose-500',     bg: 'bg-rose-100 dark:bg-rose-500/15',       text: 'text-rose-700 dark:text-rose-300' },
  { ring: 'ring-fuchsia-500',  bg: 'bg-fuchsia-100 dark:bg-fuchsia-500/15', text: 'text-fuchsia-700 dark:text-fuchsia-300' },
  { ring: 'ring-indigo-500',   bg: 'bg-indigo-100 dark:bg-indigo-500/15',   text: 'text-indigo-700 dark:text-indigo-300' },
  { ring: 'ring-teal-500',     bg: 'bg-teal-100 dark:bg-teal-500/15',       text: 'text-teal-700 dark:text-teal-300' },
  { ring: 'ring-pink-500',     bg: 'bg-pink-100 dark:bg-pink-500/15',       text: 'text-pink-700 dark:text-pink-300' },
];

export const getWeeekMemberColor = (id: string | undefined | null) => {
  const seed = id || 'unassigned';
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % WEEEK_MEMBER_PALETTE.length;
  return WEEEK_MEMBER_PALETTE[index];
};

/** Инициалы для аватара: первая буква первого и последнего слова имени. */
export const getWeeekMemberInitials = (name: string | undefined | null) => {
  if (!name) return '?';
  const trimmed = name.trim();
  if (!trimmed) return '?';
  if (trimmed.startsWith('User #')) return '?';
  const parts = trimmed.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};
