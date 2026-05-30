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
    <div className="flex items-center gap-3">
      <Switch
        checked={enabled}
        onChange={onChange}
        disabled={disabled}
        className={clsx(
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
          enabled ? 'bg-primary-600' : 'bg-gray-200',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <span
          className={clsx(
            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
            enabled ? 'translate-x-6' : 'translate-x-1'
          )}
        />
      </Switch>
      <span className="text-sm text-gray-700">🔇 Шумоподавление</span>
    </div>
  );
};