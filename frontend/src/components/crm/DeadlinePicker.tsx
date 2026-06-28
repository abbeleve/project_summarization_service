import { useState, useRef } from 'react';
import { Popover } from './Popover';

interface DeadlinePickerProps {
  value: string | undefined;
  onChange: (iso: string | null) => void;
  /** CRM не подключена — кнопка триггера должна быть серой и некликабельной. */
  disabled?: boolean;
}

const PRESETS: Array<{ label: string; days: number }> = [
  { label: 'Сегодня', days: 0 },
  { label: 'Завтра', days: 1 },
  { label: 'Неделя', days: 7 },
  { label: 'Месяц', days: 30 },
];

const isoForOffset = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

const formatRu = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });

export const DeadlinePicker = ({ value, onChange, disabled }: DeadlinePickerProps) => {
  const [mode, setMode] = useState<'picker' | 'specific'>('picker');
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <Popover
      disabled={disabled}
      trigger={(open, toggle) => {
        const hasValue = !!value;
        const disabledClasses = 'bg-gray-100 text-gray-300 ring-1 ring-dashed ring-gray-300 cursor-not-allowed dark:bg-white/[0.02] dark:text-gray-600 dark:ring-white/10';
        return (
          <button
            type="button"
            onClick={disabled ? undefined : () => {
              setMode('picker');
              toggle();
            }}
            aria-disabled={disabled}
            disabled={disabled}
            className={`group inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-medium transition-colors ${
              disabled
                ? disabledClasses
                : hasValue
                  ? 'bg-amber-100 text-amber-800 ring-1 ring-amber-300 hover:bg-amber-200 dark:bg-amber-500/15 dark:text-amber-200 dark:ring-amber-400/30 dark:hover:bg-amber-500/25'
                  : open
                    ? 'bg-gray-100 text-gray-700 ring-1 ring-gray-300 dark:bg-white/5 dark:text-gray-300 dark:ring-white/15'
                    : 'bg-gray-50 text-gray-400 ring-1 ring-dashed ring-gray-300 hover:bg-gray-100 hover:text-gray-600 dark:bg-white/[0.03] dark:text-gray-400 dark:ring-white/10 dark:hover:bg-white/5 dark:hover:text-gray-300'
            }`}
            title={disabled ? 'Сначала подключите Weeek API в Настройках' : hasValue ? 'Изменить срок' : 'Установить срок'}
          >
            <span aria-hidden>⏰</span>
            <span>{hasValue ? formatRu(value!) : 'Срок'}</span>
            {!disabled && <span className="opacity-60 text-[9px]">{open ? '▲' : '▼'}</span>}
          </button>
        );
      }}
    >
      {(close) =>
        mode === 'picker' ? (
          <div className="px-2 py-2 space-y-1">
            <p className="px-1.5 pb-1 text-[10px] uppercase tracking-wider text-gray-500">
              Дедлайн
            </p>
            {PRESETS.map((p) => {
              const iso = isoForOffset(p.days);
              const active = value === iso;
              return (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => {
                    onChange(iso);
                    close();
                  }}
                  className={`w-full text-left px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                    active
                      ? 'bg-amber-100 text-amber-800 ring-1 ring-amber-300 dark:bg-amber-500/20 dark:text-amber-100 dark:ring-amber-400/40'
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/5'
                  }`}
                >
                  📅 {p.label}
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => {
                setMode('specific');
                setTimeout(() => inputRef.current?.showPicker?.(), 50);
              }}
              className="w-full text-left px-2.5 py-1.5 rounded-md text-xs text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/5"
            >
              🗓️ Своя дата…
            </button>
            {value && (
              <button
                type="button"
                onClick={() => {
                  onChange(null);
                  close();
                }}
                className="w-full text-left px-2.5 py-1.5 rounded-md text-xs text-red-600 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-500/15"
              >
                ✕ Убрать срок
              </button>
            )}
          </div>
        ) : (
          <div className="px-2 py-2 space-y-2">
            <p className="px-1.5 text-[10px] uppercase tracking-wider text-gray-500">
              Произвольная дата
            </p>
            <input
              ref={inputRef}
              type="date"
              autoFocus
              defaultValue={value || new Date().toISOString().slice(0, 10)}
              onChange={(e) => {
                if (e.target.value) {
                  onChange(e.target.value);
                  close();
                }
              }}
              className="w-full px-2 py-1.5 rounded-md text-xs bg-white border border-gray-300 text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-400 dark:bg-white/5 dark:border-white/10 dark:text-gray-100 [color-scheme] dark:[color-scheme]"
            />
            <button
              type="button"
              onClick={() => setMode('picker')}
              className="text-[11px] text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ← Назад
            </button>
          </div>
        )
      }
    </Popover>
  );
};
