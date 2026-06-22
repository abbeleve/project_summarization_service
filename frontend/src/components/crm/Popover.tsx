import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

interface PopoverProps {
  trigger: (open: boolean, toggle: () => void) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: 'left' | 'right';
  className?: string;
  /** Если true — popover нельзя открыть (например, CRM отключена). */
  disabled?: boolean;
}

export const Popover = ({ trigger, children, align = 'left', className = '', disabled }: PopoverProps) => {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const toggle = () => {
    if (disabled) return;
    setOpen((prev) => !prev);
  };
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || disabled) return;
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, disabled]);

  return (
    <div ref={containerRef} className={`relative inline-flex ${className}`}>
      {trigger(open, toggle)}
      {open && (
        <div
          className={`absolute z-40 mt-1.5 ${
            align === 'right' ? 'right-0' : 'left-0'
          } rounded-xl bg-white border border-gray-200 shadow-lg shadow-gray-200/50 dark:bg-[#0e1622]/95 dark:border-white/10 dark:shadow-2xl dark:shadow-black/40 py-1.5 min-w-[14rem]`}
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {children(close)}
        </div>
      )}
    </div>
  );
};
