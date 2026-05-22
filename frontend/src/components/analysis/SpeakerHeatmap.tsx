import { useMemo } from 'react';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor } from '@/utils/speakerColors';

interface SpeakerHeatmapProps {
  segments: TranscriptSegment[];
  onSegmentClick?: (segment: TranscriptSegment) => void;
}

interface HeatmapCell {
  speaker: string;
  timeSlot: number;
  duration: number;
  intensity: number; // 0-1
  segment?: TranscriptSegment; // Сегмент для клика
}

export const SpeakerHeatmap = ({ segments, onSegmentClick }: SpeakerHeatmapProps) => {
  // Группируем данные для heatmap
  const heatmapData = useMemo(() => {
    if (segments.length === 0) return { cells: [], speakers: [], timeSlots: [] };

    const intervalSeconds = 60; // 1-минутные интервалы
    
    // Находим минимальное и максимальное время
    const minTime = Math.floor(Math.min(...segments.map(s => s.start)) / intervalSeconds) * intervalSeconds;
    const maxTime = Math.ceil(Math.max(...segments.map(s => s.stop)) / intervalSeconds) * intervalSeconds;
    
    // Создаём временные слоты
    const timeSlots: number[] = [];
    for (let t = minTime; t <= maxTime; t += intervalSeconds) {
      timeSlots.push(t);
    }
    
    // Получаем уникальных спикеров
    const speakers = Array.from(new Set(segments.map(s => s.Speaker)));
    
    // Создаём ячейки
    const cells: HeatmapCell[] = [];
    
    speakers.forEach(speaker => {
      timeSlots.forEach(timeSlot => {
        // Находим сегменты спикера в этом интервале
        const overlappingSegments = segments.filter(seg => {
          if (seg.Speaker !== speaker) return false;
          const overlap = Math.min(seg.stop, timeSlot + intervalSeconds) - Math.max(seg.start, timeSlot);
          return overlap > 0;
        });
        
        // Считаем общую длительность
        let duration = 0;
        overlappingSegments.forEach(seg => {
          const overlap = Math.min(seg.stop, timeSlot + intervalSeconds) - Math.max(seg.start, timeSlot);
          duration += Math.max(0, overlap);
        });
        
        const intensity = Math.min(1, duration / intervalSeconds);
        
        // Находим ближайший сегмент для клика
        const nearestSegment = overlappingSegments.length > 0
          ? overlappingSegments.reduce((nearest, current) => {
              const nearestOverlap = Math.min(nearest.stop, timeSlot + intervalSeconds) - Math.max(nearest.start, timeSlot);
              const currentOverlap = Math.min(current.stop, timeSlot + intervalSeconds) - Math.max(current.start, timeSlot);
              return currentOverlap > nearestOverlap ? current : nearest;
            })
          : undefined;
        
        if (duration > 0) {
          cells.push({ speaker, timeSlot, duration, intensity, segment: nearestSegment });
        }
      });
    });
    
    return { cells, speakers, timeSlots };
  }, [segments]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getIntensityColor = (intensity: number, speaker: string) => {
    const color = getSpeakerColor(speaker);
    const colorName = color.bg.replace('bg-', '');
    
    // Tailwind цвета для разных интенсивностей
    const colorMap: Record<string, string[]> = {
      'blue-500': ['bg-blue-100', 'bg-blue-200', 'bg-blue-300', 'bg-blue-400', 'bg-blue-500', 'bg-blue-600'],
      'green-500': ['bg-green-100', 'bg-green-200', 'bg-green-300', 'bg-green-400', 'bg-green-500', 'bg-green-600'],
      'orange-500': ['bg-orange-100', 'bg-orange-200', 'bg-orange-300', 'bg-orange-400', 'bg-orange-500', 'bg-orange-600'],
      'blue-500': ['bg-blue-100', 'bg-blue-200', 'bg-blue-300', 'bg-blue-400', 'bg-blue-500', 'bg-blue-600'],
      'pink-500': ['bg-pink-100', 'bg-pink-200', 'bg-pink-300', 'bg-pink-400', 'bg-pink-500', 'bg-pink-600'],
      'indigo-500': ['bg-indigo-100', 'bg-indigo-200', 'bg-indigo-300', 'bg-indigo-400', 'bg-indigo-500', 'bg-indigo-600'],
      'red-500': ['bg-red-100', 'bg-red-200', 'bg-red-300', 'bg-red-400', 'bg-red-500', 'bg-red-600'],
      'yellow-500': ['bg-yellow-100', 'bg-yellow-200', 'bg-yellow-300', 'bg-yellow-400', 'bg-yellow-500', 'bg-yellow-600'],
      'teal-500': ['bg-teal-100', 'bg-teal-200', 'bg-teal-300', 'bg-teal-400', 'bg-teal-500', 'bg-teal-600'],
      'cyan-500': ['bg-cyan-100', 'bg-cyan-200', 'bg-cyan-300', 'bg-cyan-400', 'bg-cyan-500', 'bg-cyan-600'],
      'rose-500': ['bg-rose-100', 'bg-rose-200', 'bg-rose-300', 'bg-rose-400', 'bg-rose-500', 'bg-rose-600'],
      'blue-500': ['bg-blue-100', 'bg-blue-200', 'bg-blue-300', 'bg-blue-400', 'bg-blue-500', 'bg-blue-600'],
      'lime-500': ['bg-lime-100', 'bg-lime-200', 'bg-lime-300', 'bg-lime-400', 'bg-lime-500', 'bg-lime-600'],
      'amber-500': ['bg-amber-100', 'bg-amber-200', 'bg-amber-300', 'bg-amber-400', 'bg-amber-500', 'bg-amber-600'],
      'emerald-500': ['bg-emerald-100', 'bg-emerald-200', 'bg-emerald-300', 'bg-emerald-400', 'bg-emerald-500', 'bg-emerald-600'],
      'sky-500': ['bg-sky-100', 'bg-sky-200', 'bg-sky-300', 'bg-sky-400', 'bg-sky-500', 'bg-sky-600'],
    };
    
    const colors = colorMap[colorName] || colorMap['blue-500'];
    const index = Math.min(5, Math.floor(intensity * 6));
    return colors[index];
  };

  if (heatmapData.cells.length === 0) {
    return null;
  }

  const { speakers, timeSlots, cells } = heatmapData;

  return (
    <div className="bg-gradient-to-r from-cyan-50 to-blue-50 dark:from-cyan-900/20 dark:to-blue-900/20 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700">
      <div className="overflow-x-auto">
        <div className="min-w-max">
          {/* Заголовки времени */}
          <div className="flex mb-2 ml-20">
            {timeSlots.map((timeSlot, idx) => (
              <div
                key={timeSlot}
                className="w-8 flex-shrink-0 text-xs text-gray-500 dark:text-gray-400 text-center"
              >
                {formatTime(timeSlot)}
              </div>
            ))}
          </div>

          {/* Строки спикеров */}
          <div className="space-y-1">
            {speakers.map(speaker => (
              <div key={speaker} className="flex items-center gap-2">
                {/* Имя спикера */}
                <div className="w-20 text-xs font-medium text-gray-700 dark:text-gray-300 truncate flex-shrink-0">
                  {speaker.replace('SPEAKER_', 'SP ')}
                </div>

                {/* Ячейки heatmap */}
                <div className="flex gap-0.5">
                  {timeSlots.map(timeSlot => {
                    const cell = cells.find(c => c.speaker === speaker && c.timeSlot === timeSlot);
                    const intensity = cell ? cell.intensity : 0;

                    return (
                      <div
                        key={`${speaker}-${timeSlot}`}
                        onClick={() => {
                          if (cell?.segment && onSegmentClick) {
                            onSegmentClick(cell.segment);
                          }
                        }}
                        className={`w-8 h-8 flex-shrink-0 rounded transition-all relative group ${
                          intensity > 0
                            ? `${getIntensityColor(intensity, speaker)} hover:scale-110 ${
                                onSegmentClick && cell?.segment ? 'cursor-pointer hover:shadow-md' : 'cursor-default'
                              }`
                            : 'bg-gray-100 dark:bg-dark-base-800'
                        }`}
                        title={
                          cell
                            ? `${speaker}: ${cell.duration.toFixed(1)} сек в ${formatTime(timeSlot)}\n${
                                onSegmentClick && cell.segment ? 'Кликните для перехода' : ''
                              }`.trim()
                            : `${speaker}: нет активности`
                        }
                      >
                        {/* Tooltip с уровнем активности */}
                        {intensity > 0 && (
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 dark:bg-dark-base-700 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10 shadow-lg">
                            {intensity >= 0.8 ? '🔥 Очень высокая' :
                             intensity >= 0.6 ? '📈 Высокая' :
                             intensity >= 0.4 ? '📊 Средняя' :
                             intensity >= 0.2 ? '📉 Низкая' : '⏸️ Минимальная'}
                            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1">
                              <div className="border-4 border-transparent border-t-gray-900 dark:border-t-gray-700"></div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Легенда */}
          <div className="flex items-center gap-2 mt-4 ml-20">
            <span className="text-xs text-gray-500 dark:text-gray-400">Активность:</span>
            <div className="flex gap-1">
              <div className="w-8 h-3 rounded flex-shrink-0 bg-gray-100 dark:bg-dark-base-700" title="Нет активности" />
              <div className="w-8 h-3 rounded flex-shrink-0 bg-blue-100 dark:bg-blue-900/30" title="Низкая" />
              <div className="w-8 h-3 rounded flex-shrink-0 bg-blue-300 dark:bg-blue-700" title="Средняя" />
              <div className="w-8 h-3 rounded flex-shrink-0 bg-blue-500" title="Высокая" />
              <div className="w-8 h-3 rounded flex-shrink-0 bg-blue-600" title="Очень высокая" />
            </div>
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-500 dark:text-gray-400 mt-3 text-center">
        Каждая ячейка показывает активность спикера в 1-минутном интервале
      </p>
    </div>
  );
};
