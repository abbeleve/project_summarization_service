import { memo } from 'react';
import { clsx } from 'clsx';
import { formatTime } from '@/utils/formatTime';

interface TranscriptSegmentProps {
  speaker: string;
  text: string;
  startTime: number;
  endTime: number;
  isActive?: boolean;
  onClick?: () => void;
}

export const TranscriptSegment = memo(({ 
  speaker, 
  text, 
  startTime, 
  endTime, 
  isActive, 
  onClick 
}: TranscriptSegmentProps) => {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-4 rounded-lg border transition-colors cursor-pointer',
        isActive 
          ? 'bg-primary-50 border-primary-300' 
          : 'bg-white border-gray-200 hover:border-gray-300'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-gray-900">{speaker}</span>
        <span className="text-xs text-gray-500">
          {formatTime(startTime)} – {formatTime(endTime)}
        </span>
      </div>
      <p className="text-gray-700 leading-relaxed">{text}</p>
    </div>
  );
});

TranscriptSegment.displayName = 'TranscriptSegment';