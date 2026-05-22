import { useState, useRef } from 'react';
import { type Annotation } from '@/api/transcripts';
import { getSpeakerColor } from '@/utils/speakerColors';

interface AnnotatedTextProps {
  text: string;
  partId: string;
  annotations: Annotation[];
  onAnnotationClick?: (annotation: Annotation) => void;
  speaker?: string;
}

const AnnotationTooltip = ({ note, speaker, children }: { note: string; speaker?: string; children: React.ReactNode }) => {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const color = speaker ? getSpeakerColor(speaker) : null;

  const show = () => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setVisible(true), 100);
  };

  const hide = () => {
    clearTimeout(timeoutRef.current);
    setVisible(false);
  };

  return (
    <span className="relative inline" onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {visible && (
        <span className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 rounded-lg shadow-lg whitespace-normal max-w-[280px] z-50 pointer-events-none ${color ? color.light + ' ' + color.text : 'bg-gray-900 dark:bg-gray-700 text-white'} text-xs leading-relaxed`}>
          💬 {note}
          <span className={`absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent ${color ? 'border-t-current' : 'border-t-gray-900 dark:border-t-gray-700'}`}
            style={color ? { borderTopColor: 'currentColor' } : undefined}
          />
        </span>
      )}
    </span>
  );
};

export const AnnotatedText = ({ text, partId, annotations, onAnnotationClick, speaker }: AnnotatedTextProps) => {
  // Фильтруем аннотации для этой части
  const partAnnotations = annotations.filter(a => a.part_id === partId);

  if (partAnnotations.length === 0) {
    return <span>{text}</span>;
  }

  const colorMap: Record<string, string> = {
    yellow: 'bg-yellow-200 dark:bg-yellow-900/40 hover:bg-yellow-300 dark:hover:bg-yellow-800/50',
    green: 'bg-green-200 dark:bg-green-900/40 hover:bg-green-300 dark:hover:bg-green-800/50',
    blue: 'bg-blue-200 dark:bg-blue-900/40 hover:bg-blue-300 dark:hover:bg-blue-800/50',
    pink: 'bg-pink-200 dark:bg-pink-900/40 hover:bg-pink-300 dark:hover:bg-pink-800/50',
    purple: 'bg-purple-200 dark:bg-purple-900/40 hover:bg-purple-300 dark:hover:bg-purple-800/50',
  };

  // Сортируем аннотации по позиции
  const sortedAnnotations = [...partAnnotations].sort((a, b) => a.start_char - b.start_char);

  // Разбиваем текст на сегменты с аннотациями
  const segments: { text: string; annotation?: Annotation }[] = [];
  let lastPos = 0;

  for (const annotation of sortedAnnotations) {
    // Текст до аннотации
    if (annotation.start_char > lastPos) {
      segments.push({
        text: text.slice(lastPos, annotation.start_char)
      });
    }

    // Аннотированный текст
    segments.push({
      text: text.slice(annotation.start_char, annotation.end_char),
      annotation
    });

    lastPos = annotation.end_char;
  }

  // Оставшийся текст
  if (lastPos < text.length) {
    segments.push({
      text: text.slice(lastPos)
    });
  }

  return (
    <>
      {segments.map((segment, idx) => (
        segment.annotation ? (
          <span
            key={idx}
            className={`relative inline px-0.5 rounded cursor-pointer transition-colors ${colorMap[segment.annotation.color || 'yellow'] || colorMap.yellow}`}
            onClick={(e) => {
              e.stopPropagation();
              onAnnotationClick?.(segment.annotation!);
            }}
          >
            {segment.annotation.note ? (
              <AnnotationTooltip note={segment.annotation.note} speaker={speaker}>
                {segment.text}
              </AnnotationTooltip>
            ) : (
              segment.text
            )}
          </span>
        ) : (
          <span key={idx}>{segment.text}</span>
        )
      ))}
    </>
  );
};
