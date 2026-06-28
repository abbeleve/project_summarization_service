import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor, getSpeakerColorBySeed } from '@/utils/speakerColors';

interface SpeakerActivityChartProps {
  segments: TranscriptSegment[];
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

export const SpeakerActivityChart = ({ segments }: SpeakerActivityChartProps) => {
  const [timeInterval, setTimeInterval] = useState<'30s' | '1m' | '2m'>('1m');

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

  // Группируем сегменты по временным интервалам
  const getActivityData = () => {
    if (segments.length === 0) return [];

    const intervalSeconds = timeInterval === '30s' ? 30 : timeInterval === '1m' ? 60 : 120;

    // Находим минимальное и максимальное время
    const minTime = Math.min(...segments.map(s => s.start));
    const maxTime = Math.max(...segments.map(s => s.stop));

    // Выравниваем базовое время по кратной intervalSeconds сетке,
    // чтобы инициализация интервалов и индексация сегментов совпадали
    const baseTime = Math.floor(minTime / intervalSeconds) * intervalSeconds;

    // Создаём временные интервалы
    const intervals: Array<{ time: string; [speaker: string]: number | string }> = [];
    const speakerSet = new Set<string>();

    segments.forEach(seg => {
      speakerSet.add(seg.Speaker);
    });

    const speakers = Array.from(speakerSet);

    // Инициализируем интервалы от baseTime (а не от minTime)
    for (let t = baseTime; t <= Math.ceil(maxTime); t += intervalSeconds) {
      const interval: any = { time: formatTime(t) };
      speakers.forEach(speaker => {
        interval[speaker] = 0;
      });
      intervals.push(interval);
    }

    // Заполняем данными
    segments.forEach(seg => {
      const intervalBucketStart = Math.floor((seg.start - baseTime) / intervalSeconds) * intervalSeconds + baseTime;
      const intervalBucketEnd = Math.floor((seg.stop - baseTime) / intervalSeconds) * intervalSeconds + baseTime;

      for (let t = intervalBucketStart; t <= intervalBucketEnd && t < maxTime; t += intervalSeconds) {
        const intervalIndex = Math.floor((t - baseTime) / intervalSeconds);
        if (intervalIndex >= 0 && intervalIndex < intervals.length) {
          const current = intervals[intervalIndex][seg.Speaker] as number || 0;
          // Считаем сколько секунд спикер говорил в этом интервале
          const intervalStart = t;
          const intervalEnd = t + intervalSeconds;
          const overlap = Math.min(seg.stop, intervalEnd) - Math.max(seg.start, intervalStart);
          intervals[intervalIndex][seg.Speaker] = current + Math.max(0, overlap);
        }
      }
    });

    return intervals;
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const data = getActivityData();
  const speakers = segments.length > 0
    ? Array.from(new Set(segments.map(s => s.Speaker)))
    : [];
  const intervalSeconds = timeInterval === '30s' ? 30 : timeInterval === '1m' ? 60 : 120;

  if (data.length === 0) {
    return null;
  }

  // Фиксированная ширина колонки: при 30с → ~5мин видно, 1м → ~10мин, 2м → ~20мин
  const BAR_GROUP_WIDTH = 60; // px на один интервал
  const chartWidth = Math.max(data.length * BAR_GROUP_WIDTH, 400);

  return (
    <div className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700 space-y-4">
      {/* Переключатель интервала */}
      <div className="flex justify-end">
        <div className="flex gap-1 bg-white dark:bg-dark-base-800 rounded-lg p-1 border border-gray-200 dark:border-dark-base-700">
          <button
            onClick={() => setTimeInterval('30s')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              timeInterval === '30s'
                ? 'bg-emerald-500 text-white'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-700'
            }`}
          >
            30с
          </button>
          <button
            onClick={() => setTimeInterval('1m')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              timeInterval === '1m'
                ? 'bg-emerald-500 text-white'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-700'
            }`}
          >
            1м
          </button>
          <button
            onClick={() => setTimeInterval('2m')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              timeInterval === '2m'
                ? 'bg-emerald-500 text-white'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-base-700'
            }`}
          >
            2м
          </button>
        </div>
      </div>

      {/* Скролляемый контейнер: max-content подстраивается под реальную ширину SVG */}
      <div className="h-64 overflow-x-auto">
        <div style={{ width: 'max-content' }}>
          <BarChart
            width={chartWidth}
            height={256}
            data={data}
            barCategoryGap={4}
            barGap={0}
            style={{ maxWidth: 'none' }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              interval={Math.max(1, Math.floor(data.length / 15))}
            />
            <YAxis
              domain={[0, intervalSeconds]}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              label={{ value: 'сек', angle: -90, position: 'insideLeft', fontSize: 12 }}
              width={40}
            />
            <Tooltip
              contentStyle={{
                borderRadius: '12px',
                border: '1px solid #e5e7eb',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                backgroundColor: 'white'
              }}
              formatter={(value: number, name: string) => [`${value.toFixed(1)} сек`, name]}
            />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={10}
            />
            {speakers.map((speaker) => {
              const color = getSpeakerHexColor(speaker);
              return (
                <Bar
                  key={speaker}
                  dataKey={speaker}
                  stackId="1"
                  fill={color}
                  radius={[0, 0, 0, 0]}
                  isAnimationActive={false}
                />
              );
            })}
          </BarChart>
        </div>
      </div>

      <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
        Показано время речи каждого спикера в разрезе временных интервалов. Цвета взяты из аватарок. Скролльте по горизонтали.
      </p>
    </div>
  );
};
