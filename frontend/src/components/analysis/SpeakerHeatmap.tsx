import { useMemo } from 'react';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor } from '@/utils/speakerColors';

interface SpeakerHeatmapProps {
  segments: TranscriptSegment[];
}

interface HeatmapCell {
  speaker: string;
  timeSlot: number;
  duration: number;
  intensity: number; // 0-1
}

export const SpeakerHeatmap = ({ segments }: SpeakerHeatmapProps) => {
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
        // Считаем сколько секунд спикер говорил в этом интервале
        let duration = 0;
        segments.forEach(seg => {
          if (seg.Speaker === speaker) {
            const overlap = Math.min(seg.stop, timeSlot + intervalSeconds) - Math.max(seg.start, timeSlot);
            duration += Math.max(0, overlap);
          }
        });
        
        const intensity = Math.min(1, duration / intervalSeconds);
        
        if (duration > 0) {
          cells.push({ speaker, timeSlot, duration, intensity });
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
      'purple-500': ['bg-purple-100', 'bg-purple-200', 'bg-purple-300', 'bg-purple-400', 'bg-purple-500', 'bg-purple-600'],
      'pink-500': ['bg-pink-100', 'bg-pink-200', 'bg-pink-300', 'bg-pink-400', 'bg-pink-500', 'bg-pink-600'],
      'indigo-500': ['bg-indigo-100', 'bg-indigo-200', 'bg-indigo-300', 'bg-indigo-400', 'bg-indigo-500', 'bg-indigo-600'],
      'red-500': ['bg-red-100', 'bg-red-200', 'bg-red-300', 'bg-red-400', 'bg-red-500', 'bg-red-600'],
      'yellow-500': ['bg-yellow-100', 'bg-yellow-200', 'bg-yellow-300', 'bg-yellow-400', 'bg-yellow-500', 'bg-yellow-600'],
      'teal-500': ['bg-teal-100', 'bg-teal-200', 'bg-teal-300', 'bg-teal-400', 'bg-teal-500', 'bg-teal-600'],
      'cyan-500': ['bg-cyan-100', 'bg-cyan-200', 'bg-cyan-300', 'bg-cyan-400', 'bg-cyan-500', 'bg-cyan-600'],
      'rose-500': ['bg-rose-100', 'bg-rose-200', 'bg-rose-300', 'bg-rose-400', 'bg-rose-500', 'bg-rose-600'],
      'violet-500': ['bg-violet-100', 'bg-violet-200', 'bg-violet-300', 'bg-violet-400', 'bg-violet-500', 'bg-violet-600'],
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
    return (
      <div className="bg-gradient-to-r from-cyan-50 to-blue-50 rounded-2xl p-5 border border-gray-200">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center shadow-md">
            <span className="text-lg">🔥</span>
          </div>
          <h4 className="text-lg font-bold text-gray-900">Тепловая карта активности</h4>
        </div>
        <div className="text-center text-gray-500 py-12">
          Нет данных для отображения
        </div>
      </div>
    );
  }

  const { speakers, timeSlots, cells } = heatmapData;

  return (
    <div className="bg-gradient-to-r from-cyan-50 to-blue-50 rounded-2xl p-5 border border-gray-200">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center shadow-md">
          <span className="text-lg">🔥</span>
        </div>
        <h4 className="text-lg font-bold text-gray-900">Тепловая карта активности</h4>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-full">
          {/* Заголовки времени */}
          <div className="flex mb-2 ml-20">
            {timeSlots.map((timeSlot, idx) => (
              <div
                key={timeSlot}
                className="flex-1 text-xs text-gray-500 text-center min-w-[30px]"
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
                <div className="w-20 text-xs font-medium text-gray-700 truncate flex-shrink-0">
                  {speaker.replace('SPEAKER_', 'SP ')}
                </div>
                
                {/* Ячейки heatmap */}
                <div className="flex flex-1 gap-0.5">
                  {timeSlots.map(timeSlot => {
                    const cell = cells.find(c => c.speaker === speaker && c.timeSlot === timeSlot);
                    const intensity = cell ? cell.intensity : 0;
                    
                    return (
                      <div
                        key={`${speaker}-${timeSlot}`}
                        className={`flex-1 h-8 rounded transition-all ${
                          intensity > 0
                            ? `${getIntensityColor(intensity, speaker)} hover:scale-110 cursor-pointer`
                            : 'bg-gray-100'
                        }`}
                        title={
                          cell
                            ? `${speaker}: ${cell.duration.toFixed(1)} сек в ${formatTime(timeSlot)}`
                            : `${speaker}: нет активности`
                        }
                      />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Легенда */}
          <div className="flex items-center gap-2 mt-4 ml-20">
            <span className="text-xs text-gray-500">Активность:</span>
            <div className="flex gap-1">
              <div className="w-6 h-3 rounded bg-gray-100" title="Нет активности" />
              <div className="w-6 h-3 rounded bg-blue-100" title="Низкая" />
              <div className="w-6 h-3 rounded bg-blue-300" title="Средняя" />
              <div className="w-6 h-3 rounded bg-blue-500" title="Высокая" />
              <div className="w-6 h-3 rounded bg-blue-600" title="Очень высокая" />
            </div>
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-500 mt-3 text-center">
        Каждая ячейка показывает активность спикера в 1-минутном интервале
      </p>
    </div>
  );
};
