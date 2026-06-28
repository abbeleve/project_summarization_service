import { Switch } from '@headlessui/react';
import { clsx } from 'clsx';

interface NoiseSuppressionToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  disabled?: boolean;
}

export const NoiseSuppressionToggle = ({
  enabled,
  onChange,
  disabled
}: NoiseSuppressionToggleProps) => {
  return (
    <div className="flex items-center gap-3 select-none">
      <Switch
        checked={enabled}
        onChange={onChange}
        disabled={disabled}
        className={clsx(
          'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-all duration-300',
          'border',
          enabled
            ? 'bg-blue-500 border-blue-400/50 shadow-[0_0_18px_-2px_rgba(59,130,246,0.35)]'
            : 'bg-[#1a1a1d] border-[rgba(255,255,255,0.08)]',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
        aria-label="Шумоподавление"
      >
        <span
          className={clsx(
            'inline-flex items-center justify-center h-4 w-4 transform rounded-full bg-white transition-transform duration-300',
            enabled
              ? 'translate-x-6 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.4)]'
              : 'translate-x-1'
          )}
        >
          {enabled && (
            <svg
              className="w-2.5 h-2.5 text-blue-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </span>
      </Switch>

      <span
        className={clsx(
          'text-[13px] font-medium tracking-[0.005em] transition-colors',
          enabled ? 'text-blue-400' : 'text-[#a0a0a8]',
          disabled && 'opacity-60'
        )}
      >
        Шумоподавление
      </span>
    </div>
  );
};
