import type { ReactNode } from 'react';

interface StepDotProps {
  active: boolean;
  done: boolean;
  disabled?: boolean;
  /** CRM не подключена. Принудительно серый, как disabled, но в приоритете
   *  (на случай, если `active/done` уже выставлен из предыдущего состояния). */
  locked?: boolean;
  loading?: boolean;
  icon: string;
  label: string;
  open?: boolean;
  /** Контент выпадающего списка. Рендерится, если `open === true`. */
  dropdown?: ReactNode;
  onClick: () => void;
}

export const StepDot = ({ active, done, disabled, locked, loading, icon, label, open, dropdown, onClick }: StepDotProps) => {
  const inactive = locked || disabled;
  const stateClass = inactive
    ? 'bg-gray-100 text-gray-300 dark:bg-white/[0.02] dark:text-gray-600 cursor-not-allowed'
    : done
      ? 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-300 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-400/30 hover:bg-emerald-200 dark:hover:bg-emerald-500/25'
      : active
        ? 'bg-indigo-100 text-indigo-700 ring-1 ring-indigo-300 dark:bg-indigo-500/15 dark:text-indigo-300 dark:ring-indigo-400/30 hover:bg-indigo-200 dark:hover:bg-indigo-500/25'
        : 'bg-gray-100 text-gray-500 ring-1 ring-dashed ring-gray-300 dark:bg-white/[0.04] dark:text-gray-400 dark:ring-white/15 hover:bg-gray-200 dark:hover:bg-white/[0.08]';

  return (
    <div className="relative inline-flex">
      <button
        type="button"
        onClick={inactive ? undefined : onClick}
        aria-disabled={inactive}
        disabled={inactive}
        title={locked ? 'Сначала подключите Weeek API в Настройках' : undefined}
        className={`inline-flex items-center gap-1.5 pl-2 pr-3 h-8 rounded-full text-xs font-medium transition-colors ${stateClass}`}
      >
        <span className={`w-4 h-4 rounded-full inline-flex items-center justify-center text-[10px] ${done ? 'bg-emerald-500 text-white' : active ? 'bg-white/40 dark:bg-white/10' : 'bg-gray-200 dark:bg-white/5'}`}>
          {done ? '✓' : loading ? '…' : icon}
        </span>
        <span className="max-w-[12rem] truncate">{label}</span>
        {!inactive && <span className="text-[9px] opacity-60">{open ? '▲' : '▼'}</span>}
      </button>
      {open && dropdown}
    </div>
  );
};

export const StepSeparator = ({ active }: { active: boolean }) => (
  <span className={`w-4 h-px ${active ? 'bg-emerald-400 dark:bg-emerald-400/60' : 'bg-gray-300 dark:bg-white/10'}`} />
);
