import { type Annotation } from '@/api/transcripts';

interface AnnotatedTextProps {
  text: string;
  partId: string;
  annotations: Annotation[];
  onAnnotationClick?: (annotation: Annotation) => void;
}

export const AnnotatedText = ({ text, partId, annotations, onAnnotationClick }: AnnotatedTextProps) => {
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
            className={`px-0.5 rounded cursor-pointer transition-colors ${colorMap[segment.annotation.color || 'yellow'] || colorMap.yellow}`}
            title={segment.annotation.note || 'Подчёркнутый текст'}
            onClick={(e) => {
              e.stopPropagation();
              onAnnotationClick?.(segment.annotation!);
            }}
          >
            {segment.text}
          </span>
        ) : (
          <span key={idx}>{segment.text}</span>
        )
      ))}
    </>
  );
};
