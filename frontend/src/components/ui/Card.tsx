import { type ReactNode } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  padded?: boolean;
}

export const Card = ({ children, className, hover = false, padded = true }: CardProps) => {
  return (
    <div
      className={twMerge(
        clsx(
          'bg-white dark:bg-dark-base-800 rounded-xl border border-gray-200 dark:border-dark-base-700 shadow-sm',
          hover && 'hover:shadow-md transition-shadow',
          padded && 'p-4',
          className
        )
      )}
    >
      {children}
    </div>
  );
};