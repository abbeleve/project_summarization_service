import { memo } from 'react';
import { clsx } from 'clsx';
import { formatTime } from '@/utils/formatTime';
import { getSpeakerColor, getSpeakerColorBySeed } from '@/utils/speakerColors';
import { AnnotatedText } from './AnnotatedText';
import { type Annotation } from '@/api/transcripts';

interface TranscriptSegmentProps {
  speaker: string;
  text: string;
  startTime: number;
  endTime: number;
  isActive?: boolean;
  partId?: string;
  avatarUrl?: string | null;
  colorSeed?: string | null;       // user_id для стабильного цвета
  dominantColor?: string | null;   // hex-цвет из аватарки
  annotations?: Annotation[];
  onAnnotationClick?: (annotation: Annotation) => void;
  onClick?: () => void;
  onCreateFullAnnotation?: (partId: string, text: string) => void;
}

export const TranscriptSegment = memo(({
  speaker,
  text,
  startTime,
  endTime,
  isActive,
  partId,
  avatarUrl,
  colorSeed,
  dominantColor,
  annotations = [],
  onAnnotationClick,
  onClick,
  onCreateFullAnnotation
}: TranscriptSegmentProps) => {
  // Цвет: если есть dominantColor из аватарки — используем его, иначе — хеш от seed/speaker
  const paletteColor = colorSeed ? getSpeakerColorBySeed(colorSeed) : getSpeakerColor(speaker);
  const color = dominantColor
    ? { bg: '', light: '', text: '' } // не нужны Tailwind-классы, используем inline-style
    : paletteColor;

  return (
    <div
      data-part-id={partId}
      onClick={onClick}
      className={clsx(
        'p-4 rounded-xl border transition-all cursor-pointer group',
        isActive
          ? 'bg-primary-50 border-primary-300 shadow-md dark:bg-primary-900/20 dark:border-primary-700'
          : 'bg-white dark:bg-dark-base-800 border-gray-200 dark:border-dark-base-700 hover:border-gray-300 dark:hover:border-dark-base-600 hover:shadow-lg'
      )}
    >
      <div className="flex items-start gap-3 mb-3">
        {/* Цветной кружок спикера / аватарка */}
        {avatarUrl ? (
          <div className="w-8 h-8 rounded-full flex-shrink-0 overflow-hidden shadow-sm ring-2 ring-white dark:ring-gray-700">
            <img
              src={avatarUrl}
              alt={speaker}
              className="w-full h-full object-cover"
              onError={(e) => {
                // Если аватарка не загрузилась — показываем инициалы
                (e.target as HTMLImageElement).style.display = 'none';
                (e.target as HTMLImageElement).parentElement!.classList.add(...color.bg.split(' '));
                (e.target as HTMLImageElement).parentElement!.innerHTML =
                  `<span class="text-white text-xs font-bold">${speaker.slice(0, 2).toUpperCase()}</span>`;
              }}
            />
          </div>
        ) : (
          <div className={clsx(
            'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm',
            color.bg
          )}>
            <span className="text-white text-xs font-bold">
              {speaker.replace('SPEAKER_', '').slice(0, 2)}
            </span>
          </div>
        )}

        {/* Информация о спикере и времени */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-gray-900 dark:text-white">{speaker}</span>
            <div className="flex items-center gap-2">
              {partId && onCreateFullAnnotation && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onCreateFullAnnotation(partId, text);
                  }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-0.5 rounded text-xs font-medium bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-800/50"
                  title="Подчеркнуть всю реплику"
                >
                  🚩
                </button>
              )}
              <span
                style={dominantColor ? {
                  backgroundColor: `${dominantColor}22`,
                  color: dominantColor,
                } : undefined}
                className={clsx(
                  'px-2 py-1 rounded-md text-xs font-medium',
                  !dominantColor && color.light,
                  !dominantColor && color.text,
                )}
              >
                {formatTime(startTime)} – {formatTime(endTime)}
              </span>
            </div>
          </div>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed text-sm select-text">
            {partId ? (
              <AnnotatedText
                text={text}
                partId={partId}
                annotations={annotations}
                onAnnotationClick={onAnnotationClick}
                speaker={speaker}
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