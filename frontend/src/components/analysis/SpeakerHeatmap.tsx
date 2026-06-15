import { useMemo } from 'react';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor, getSpeakerColorBySeed } from '@/utils/speakerColors';

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

const getTailwindColorHex = (colorName: string): string => {
  const colorMap: Record<string, string> = {
    'blue-500': '#3B82F6',
    'green-500': '#10B981',
    'orange-500': '#F97316',
    'purple-500': '#A855F7',
    'pink-500': '#EC4899',
    'indigo-500': '#6366F1',
    'red-500': '#EF4444',
    'yellow-500': '#EAB308',
    'teal-500': '#14B8A6',
    'cyan-500': '#06B6D4',
    'rose-500': '#F43F5E',
    'violet-500': '#8B5CF6',
    'lime-500': '#84CC16',
    'amber-500': '#F59E0B',
    'emerald-500': '#10B981',
    'sky-500': '#0EA5E9',
    'fuchsia-500': '#D946EF',
  };
  return colorMap[colorName] || '#3B82F6';
};

export const SpeakerHeatmap = ({ segments, onSegmentClick }: SpeakerHeatmapProps) => {
  // Строим lookup цвета из аватарок (аналогично SpeakerDistributionChart)
  const colorSeedLookup: Record<string, string | null | undefined> = {};
  const dominantColorLookup: Record<string, string | null | undefined> = {};
  for (const seg of segments) {
    if (seg.Speaker) {
      if (!colorSeedLookup[seg.Speaker]) colorSeedLookup[seg.Speaker] = seg.colorSeed;
      if (!dominantColorLookup[seg.Speaker]) dominantColorLookup[seg.Speaker] = seg.dominantColor;
    }
  }

  // Получаем цвет спикера с приоритетом: dominantColor из аватарки > хеш от user_id > хеш от имени
  const getSpeakerHexColor = (speaker: string): string => {
    const dominant = dominantColorLookup[speaker];
    if (dominant) return dominant;
    const seed = colorSeedLookup[speaker];
    const color = seed ? getSpeakerColorBySeed(seed) : getSpeakerColor(speaker);
    return getTailwindColorHex(color.bg.replace('bg-', ''));
  };

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

  const getIntensityStyle = (intensity: number, speaker: string): React.CSSProperties => {
    const baseColor = getSpeakerHexColor(speaker);
    const opacity = 0.08 + intensity * 0.72; // от 0.08 до 0.8
    return {
      backgroundColor: baseColor,
      opacity,
    };
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

          {/* Строки спикеров (pt-7 чтобы тултип верхнего ряда не обрезался) */}
          <div className="space-y-1 pt-7">
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

                    if (intensity > 0) {
                      const bgColor = getIntensityStyle(intensity, speaker);
                      return (
                        <div
                          key={`${speaker}-${timeSlot}`}
                          onClick={() => {
                            if (cell?.segment && onSegmentClick) {
                              onSegmentClick(cell.segment);
                            }
                          }}
                          className={`w-8 h-8 flex-shrink-0 rounded relative group hover:scale-110 transition-transform ${
                            onSegmentClick && cell?.segment ? 'cursor-pointer hover:shadow-md' : 'cursor-default'
                          }`}
                          title={`${speaker}: ${cell!.duration.toFixed(1)} сек в ${formatTime(timeSlot)}\n${
                            onSegmentClick && cell.segment ? 'Кликните для перехода' : ''
                          }`.trim()}
                        >
                          {/* Фон с opacity — вынесен в отдельный слой, чтобы не влиять на тултип */}
                          <div
                            className="absolute inset-0 rounded"
                            style={bgColor}
                          />
                          {/* Tooltip с уровнем активности — без наследования opacity */}
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 dark:bg-dark-base-700 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20 shadow-lg">
                            {intensity >= 0.8 ? '🔥 Очень высокая' :
                             intensity >= 0.6 ? '📈 Высокая' :
                             intensity >= 0.4 ? '📊 Средняя' :
                             intensity >= 0.2 ? '📉 Низкая' : '⏸️ Минимальная'}
                            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1">
                              <div className="border-4 border-transparent border-t-gray-900 dark:border-t-gray-700"></div>
                            </div>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={`${speaker}-${timeSlot}`}
                        className="w-8 h-8 flex-shrink-0 rounded bg-gray-100 dark:bg-dark-base-800"
                        title={`${speaker}: нет активности`}
                      />
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
              {[0, 0.2, 0.4, 0.6, 0.8].map(level => (
                <div
                  key={level}
                  className="w-8 h-3 rounded flex-shrink-0 border border-gray-200 dark:border-gray-600"
                  style={
                    level === 0
                      ? { backgroundColor: '#f3f4f6' }
                      : { backgroundColor: '#3B82F6', opacity: 0.1 + level * 0.7 }
                  }
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-500 dark:text-gray-400 mt-3 text-center">
        Каждая ячейка показывает активность спикера в 1-минутном интервале. Цвета взяты из аватарок.
      </p>
    </div>
  );
};
