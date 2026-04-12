import { memo } from 'react';
import { clsx } from 'clsx';
import { formatTime } from '@/utils/formatTime';
import { getSpeakerColor } from '@/utils/speakerColors';
import { AnnotatedText } from './AnnotatedText';
import { type Annotation } from '@/api/transcripts';

interface TranscriptSegmentProps {
  speaker: string;
  text: string;
  startTime: number;
  endTime: number;
  isActive?: boolean;
  partId?: string;
  annotations?: Annotation[];
  onAnnotationClick?: (annotation: Annotation) => void;
  onClick?: () => void;
}

export const TranscriptSegment = memo(({
  speaker,
  text,
  startTime,
  endTime,
  isActive,
  partId,
  annotations = [],
  onAnnotationClick,
  onClick
}: TranscriptSegmentProps) => {
  const color = getSpeakerColor(speaker);

  return (
    <div
      data-part-id={partId}
      onClick={onClick}
      className={clsx(
        'p-4 rounded-xl border transition-all cursor-pointer group',
        isActive
          ? 'bg-primary-50 border-primary-300 shadow-md dark:bg-primary-900/20 dark:border-primary-700'
          : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-lg'
      )}
    >
      <div className="flex items-start gap-3 mb-3">
        {/* Цветной кружок спикера */}
        <div className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm',
          color.bg
        )}>
          <span className="text-white text-xs font-bold">
            {speaker.replace('SPEAKER_', '').slice(0, 2)}
          </span>
        </div>

        {/* Информация о спикере и времени */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-gray-900 dark:text-white">{speaker}</span>
            <span className={clsx(
              'px-2 py-1 rounded-md text-xs font-medium',
              color.light,
              color.text
            )}>
              {formatTime(startTime)} – {formatTime(endTime)}
            </span>
          </div>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed text-sm select-text">
            {partId ? (
              <AnnotatedText
                text={text}
                partId={partId}
                annotations={annotations}
                onAnnotationClick={onAnnotationClick}
              />
            ) : (
              text
            )}
          </p>
        </div>
      </div>
    </div>
  );
});

TranscriptSegment.displayName = 'TranscriptSegment';