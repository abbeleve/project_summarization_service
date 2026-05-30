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
        'py-2.5 transition-colors cursor-pointer group border-b border-gray-100 dark:border-dark-base-750/60 last:border-b-0',
        isActive
          ? 'bg-primary-50 dark:bg-primary-900/20'
          : 'hover:bg-gray-50/50 dark:hover:bg-dark-base-800/30'
      )}
    >
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
        {/* Цветной кружок спикера / аватарка — row 1, col 1 */}
        {avatarUrl ? (
          <div className="w-8 h-8 rounded-full overflow-hidden shadow-sm ring-2 ring-white dark:ring-gray-700">
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
            'w-8 h-8 rounded-full flex items-center justify-center shadow-sm',
            color.bg
          )}>
            <span className="text-white text-xs font-bold">
              {speaker.replace('SPEAKER_', '').slice(0, 2)}
            </span>
          </div>
        )}

        {/* Имя спикера и время — row 1, col 2 */}
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold text-gray-900 dark:text-white truncate">{speaker}</span>
          <span className="text-gray-400 dark:text-gray-500 text-sm whitespace-nowrap flex-shrink-0">
            {formatTime(startTime)} – {formatTime(endTime)}
          </span>
          {partId && onCreateFullAnnotation && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onCreateFullAnnotation(partId, text);
              }}
              className="opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800/50 flex-shrink-0 ml-auto"
              title="Подчеркнуть всю реплику"
            >
              🚩
            </button>
          )}
        </div>

        {/* Текст — row 2, вся ширина (на одном уровне с аватаркой) */}
        <p className="col-span-full text-gray-700 dark:text-gray-300 leading-relaxed text-base select-text">
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
  );
});

TranscriptSegment.displayName = 'TranscriptSegment';