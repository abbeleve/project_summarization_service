import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor } from '@/utils/speakerColors';

interface SpeakerActivityChartProps {
  segments: TranscriptSegment[];
}

const getTailwindColorHex = (colorName: string): string => {
  const colorMap: Record<string, string> = {
    'blue-500': '#3B82F6',
    'green-500': '#10B981',
    'orange-500': '#F97316',
    'blue-500': '#A855F7',
    'pink-500': '#EC4899',
    'indigo-500': '#6366F1',
    'red-500': '#EF4444',
    'yellow-500': '#EAB308',
    'teal-500': '#14B8A6',
    'cyan-500': '#06B6D4',
    'rose-500': '#F43F5E',
    'blue-500': '#8B5CF6',
    'lime-500': '#84CC16',
    'amber-500': '#F59E0B',
    'emerald-500': '#10B981',
    'sky-500': '#0EA5E9',
  };
  return colorMap[colorName] || '#3B82F6';
};

export const SpeakerActivityChart = ({ segments }: SpeakerActivityChartProps) => {
  const [timeInterval, setTimeInterval] = useState<'30s' | '1m' | '2m'>('1m');

  // Группируем сегменты по временным интервалам
  const getActivityData = () => {
    if (segments.length === 0) return [];

    const intervalSeconds = timeInterval === '30s' ? 30 : timeInterval === '1m' ? 60 : 120;
    
    // Находим минимальное и максимальное время
    const minTime = Math.min(...segments.map(s => s.start));
    const maxTime = Math.max(...segments.map(s => s.stop));
    
    // Создаём временные интервалы
    const intervals: Array<{ time: string; [speaker: string]: number | string }> = [];
    const speakerSet = new Set<string>();
    
    segments.forEach(seg => {
      speakerSet.add(seg.Speaker);
    });
    
    const speakers = Array.from(speakerSet);
    
    // Инициализируем интервалы
    for (let t = Math.floor(minTime); t <= Math.ceil(maxTime); t += intervalSeconds) {
      const interval: any = { time: formatTime(t) };
      speakers.forEach(speaker => {
        interval[speaker] = 0;
      });
      intervals.push(interval);
    }
    
    // Заполняем данными
    segments.forEach(seg => {
      const startInterval = Math.floor(seg.start / intervalSeconds) * intervalSeconds;
      const endInterval = Math.floor(seg.stop / intervalSeconds) * intervalSeconds;
      
      for (let t = startInterval; t <= endInterval && t < maxTime; t += intervalSeconds) {
        const intervalIndex = Math.floor((t - Math.floor(minTime)) / intervalSeconds);
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

  if (data.length === 0) {
    return null;
  }

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

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              {speakers.map((speaker, idx) => {
                const color = getTailwindColorHex(getSpeakerColor(speaker).bg.replace('bg-', ''));
                return (
                  <linearGradient key={speaker} id={`color${speaker}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.8}/>
                    <stop offset="95%" stopColor={color} stopOpacity={0.1}/>
                  </linearGradient>
                );
              })}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis 
              dataKey="time" 
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              label={{ value: 'сек', angle: -90, position: 'insideLeft', fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: '12px',
                border: '1px solid #e5e7eb',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                backgroundColor: 'white'
              }}
              formatter={(value: number) => `${value.toFixed(1)} сек`}
            />
            <Legend 
              verticalAlign="top" 
              height={36}
              iconType="circle"
              iconSize={10}
            />
            {speakers.map((speaker, idx) => {
              const color = getTailwindColorHex(getSpeakerColor(speaker).bg.replace('bg-', ''));
              return (
                <Area
                  key={speaker}
                  type="monotone"
                  dataKey={speaker}
                  stackId="1"
                  stroke={color}
                  fill={`url(#color${speaker})`}
                  strokeWidth={2}
                />
              );
            })}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
        Показано время речи каждого спикера в разрезе временных интервалов
      </p>
    </div>
  );
};
