import { useState } from 'react';
import { PieChart, Pie, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor } from '@/utils/speakerColors';
import { SpeakerActivityChart } from './SpeakerActivityChart';
import { SpeakerHeatmap } from './SpeakerHeatmap';

interface SpeakerDistributionChartProps {
  segments: TranscriptSegment[];
}

export const SpeakerDistributionChart = ({ segments }: SpeakerDistributionChartProps) => {
  const [view, setView] = useState<'distribution' | 'activity' | 'heatmap'>('distribution');
  const speakerTimes: Record<string, number> = {};

  segments.forEach(seg => {
    const speaker = seg.Speaker || 'UNKNOWN';
    const duration = seg.stop - seg.start;
    speakerTimes[speaker] = (speakerTimes[speaker] || 0) + duration;
  });

  const data: Array<{ name: string; value: number; fill: string; percent: string }> = [];
  const entries = Object.entries(speakerTimes);

  for (let idx = 0; idx < entries.length; idx++) {
    const [name, value] = entries[idx];
    const color = getSpeakerColor(name);
    // Конвертируем Tailwind цвет в hex для Recharts
    const colorHex = getTailwindColorHex(color.bg.replace('bg-', ''));
    data.push({
      name,
      value,
      fill: colorHex,
      percent: '0'
    });
  }

  let total = 0;
  for (let i = 0; i < data.length; i++) {
    total += data[i].value;
  }

  for (let i = 0; i < data.length; i++) {
    data[i].percent = ((data[i].value / total) * 100).toFixed(1);
  }

  if (data.length === 0) {
    return (
      <div className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-2xl p-5 border border-gray-200">
        <div className="text-center text-gray-500 py-12">
          Нет данных о спикерах
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-2xl p-5 border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-blue-500 flex items-center justify-center shadow-md">
            <span className="text-lg">
              {view === 'distribution' ? '🥧' : view === 'activity' ? '📈' : '🔥'}
            </span>
          </div>
          <h4 className="text-lg font-bold text-gray-900">
            {view === 'distribution'
              ? 'Распределение времени'
              : view === 'activity'
                ? 'Активность по времени'
                : 'Тепловая карта'}
          </h4>
        </div>
        
        {/* Переключатель видов */}
        <div className="flex gap-1 bg-white rounded-lg p-1 border border-gray-200">
          <button
            onClick={() => setView('distribution')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1 ${
              view === 'distribution'
                ? 'bg-indigo-500 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
            title="Распределение"
          >
            <span>🥧</span>
          </button>
          <button
            onClick={() => setView('activity')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1 ${
              view === 'activity'
                ? 'bg-indigo-500 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
            title="Активность по времени"
          >
            <span>📈</span>
          </button>
          <button
            onClick={() => setView('heatmap')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1 ${
              view === 'heatmap'
                ? 'bg-indigo-500 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
            title="Тепловая карта"
          >
            <span>🔥</span>
          </button>
        </div>
      </div>

      {view === 'distribution' ? (
        <>
          <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={4}
              dataKey="value"
              strokeWidth={0}
            >
            </Pie>
            <Tooltip
              formatter={(value: number | undefined) => `${value?.toFixed(1)} сек`}
              labelFormatter={(label) => `Спикер: ${label}`}
              contentStyle={{
                borderRadius: '12px',
                border: '1px solid #e5e7eb',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
              }}
            />
            <Legend 
              verticalAlign="bottom" 
              height={36}
              iconType="circle"
              iconSize={10}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Table view */}
      <div className="mt-4 border-t border-gray-200 pt-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500">
              <th className="pb-2">Спикер</th>
              <th className="pb-2 text-right">Время</th>
              <th className="pb-2 text-right">Доля</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, idx) => (
              <tr key={idx} className="border-t border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="py-3 flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full shadow-sm"
                    style={{ backgroundColor: item.fill }}
                  />
                  <span className="font-medium text-gray-900">{item.name}</span>
                </td>
                <td className="py-3 text-right text-gray-700">{item.value.toFixed(1)} сек</td>
                <td className="py-3 text-right font-medium text-gray-900">{item.percent}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
        </>
      ) : view === 'activity' ? (
        <SpeakerActivityChart segments={segments} />
      ) : (
        <SpeakerHeatmap segments={segments} />
      )}
    </div>
  );
};

// Helper function для конвертации Tailwind цветов в hex
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
  };
  return colorMap[colorName] || '#3B82F6';
};