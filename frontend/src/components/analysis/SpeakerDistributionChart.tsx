import { useState } from 'react';
import { type TranscriptSegment } from '@/types/transcript';
import { getSpeakerColor, getSpeakerColorBySeed } from '@/utils/speakerColors';
import { SpeakerActivityChart } from './SpeakerActivityChart';
import { SpeakerHeatmap } from './SpeakerHeatmap';

interface SpeakerDistributionChartProps {
  segments: TranscriptSegment[];
  onSegmentClick?: (segment: TranscriptSegment) => void;
}

export const SpeakerDistributionChart = ({ segments, onSegmentClick }: SpeakerDistributionChartProps) => {
  const [view, setView] = useState<'distribution' | 'activity' | 'heatmap'>('distribution');
  const speakerTimes: Record<string, number> = {};

  segments.forEach(seg => {
    const speaker = seg.Speaker || 'UNKNOWN';
    const duration = seg.stop - seg.start;
    speakerTimes[speaker] = (speakerTimes[speaker] || 0) + duration;
  });

  const data: Array<{ name: string; value: number; fill: string; percent: string; avatarUrl?: string | null }> = [];
  const entries = Object.entries(speakerTimes);
  // Build a lookup: first segment with this speaker → get its avatarUrl / dominantColor
  const avatarLookup: Record<string, string | null | undefined> = {};
  const colorSeedLookup: Record<string, string | null | undefined> = {};
  const dominantColorLookup: Record<string, string | null | undefined> = {};
  for (const seg of segments) {
    if (seg.Speaker) {
      if (!avatarLookup[seg.Speaker]) avatarLookup[seg.Speaker] = seg.avatarUrl;
      if (!colorSeedLookup[seg.Speaker]) colorSeedLookup[seg.Speaker] = seg.colorSeed;
      if (!dominantColorLookup[seg.Speaker]) dominantColorLookup[seg.Speaker] = seg.dominantColor;
    }
  }

  for (let idx = 0; idx < entries.length; idx++) {
    const [name, value] = entries[idx];

    // Приоритет: dominantColor из аватарки > хеш от user_id > хеш от имени
    let colorHex: string;
    const dominant = dominantColorLookup[name];
    if (dominant) {
      colorHex = dominant;
    } else {
      const seed = colorSeedLookup[name];
      const color = seed ? getSpeakerColorBySeed(seed) : getSpeakerColor(name);
      colorHex = getTailwindColorHex(color.bg.replace('bg-', ''));
    }

    data.push({
      name,
      value,
      fill: colorHex,
      percent: '0',
      avatarUrl: avatarLookup[name]
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
    <div className="bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-900/20 dark:to-blue-900/20 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-blue-500 flex items-center justify-center shadow-md">
            <span className="text-lg">
              {view === 'distribution' ? '🥧' : view === 'activity' ? '📈' : '🔥'}
            </span>
          </div>
          <h4 className="text-lg font-bold text-gray-900 dark:text-white">
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
          {/* Rainbow chart — semi-circular arc divided by speakers */}
          <RainbowChart data={data} />

      {/* Table view */}
      <div className="mt-4 border-t border-gray-200 dark:border-dark-base-700 pt-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 dark:text-gray-400">
              <th className="pb-2">Спикер</th>
              <th className="pb-2 text-right">Время</th>
              <th className="pb-2 text-right">Доля</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, idx) => (
              <tr key={idx} className="border-t border-gray-100 dark:border-dark-base-700 hover:bg-gray-50 dark:hover:bg-dark-base-800 transition-colors">
                <td className="py-3 flex items-center gap-2">
                  {item.avatarUrl ? (
                    <div className="w-7 h-7 rounded-full overflow-hidden flex-shrink-0 shadow-sm ring-1 ring-white">
                      <img
                        src={item.avatarUrl}
                        alt={item.name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                          const parent = (e.target as HTMLImageElement).parentElement!;
                          parent.innerHTML = `<span class="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold" style="background-color:${item.fill}">${item.name.slice(0, 2).toUpperCase()}</span>`;
                        }}
                      />
                    </div>
                  ) : (
                    <span
                      className="w-3 h-3 rounded-full shadow-sm flex-shrink-0"
                      style={{ backgroundColor: item.fill }}
                    />
                  )}
                  <span className="font-medium text-gray-900 dark:text-white">{item.name}</span>
                </td>
                <td className="py-3 text-right text-gray-700 dark:text-gray-300">{item.value.toFixed(1)} сек</td>
                <td className="py-3 text-right font-medium text-gray-900 dark:text-white">{item.percent}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
        </>
      ) : view === 'activity' ? (
        <SpeakerActivityChart segments={segments} />
      ) : (
        <SpeakerHeatmap segments={segments} onSegmentClick={onSegmentClick} />
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

/** RainbowChart — полукруглая радуга, где каждый спикер занимает сегмент */
const RainbowChart = ({ data }: { data: Array<{ name: string; value: number; fill: string; percent: string }> }) => {
  if (data.length === 0) return null;

  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) return null;

  const svgWidth = 480;
  const svgHeight = 280;
  const cx = svgWidth / 2;
  const cy = 210;
  const outerR = 140;
  const innerR = 78;

  const totalArcDeg = 230;
  const totalArc = (totalArcDeg / 180) * Math.PI; // ~4.014 рад
  const startAngle = (3 * Math.PI / 2) - (totalArc / 2); // центр вверху (3π/2)

  let currentAngle = startAngle;
  const gapWidth = 3; // px — одинаковый зазор везде

  const segments = data.map((item, idx) => {
    const rawAngle = (item.value / total) * totalArc;
    const a1 = currentAngle;
    const a2 = currentAngle + rawAngle;
    currentAngle = a2;

    // Равномерный зазор: внешняя дуга ужимается меньше, внутренняя — больше
    const outerGap = gapWidth / 2 / outerR;
    const innerGap = gapWidth / 2 / innerR;

    const ao1 = a1 + outerGap;
    const ao2 = a2 - outerGap;
    const ai1 = a1 + innerGap;
    const ai2 = a2 - innerGap;

    const effectiveAngle = rawAngle - outerGap - outerGap;
    if (effectiveAngle <= 0) return null;

    const largeArc = effectiveAngle > Math.PI ? 1 : 0;

    // Внешняя дуга
    const x1o = cx + outerR * Math.cos(ao1);
    const y1o = cy + outerR * Math.sin(ao1);
    const x2o = cx + outerR * Math.cos(ao2);
    const y2o = cy + outerR * Math.sin(ao2);

    // Внутренняя дуга
    const x1i = cx + innerR * Math.cos(ai1);
    const y1i = cy + innerR * Math.sin(ai1);
    const x2i = cx + innerR * Math.cos(ai2);
    const y2i = cy + innerR * Math.sin(ai2);

    // Позиция метки (середина сегмента, середина толщины)
    const midAngle = (a1 + a2) / 2;
    const labelR = (outerR + innerR) / 2;
    const labelX = cx + labelR * Math.cos(midAngle);
    const labelY = cy + labelR * Math.sin(midAngle);

    const color = item.fill;

    const path = [
      `M ${x1o.toFixed(1)} ${y1o.toFixed(1)}`,
      `A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2o.toFixed(1)} ${y2o.toFixed(1)}`,
      `L ${x2i.toFixed(1)} ${y2i.toFixed(1)}`,
      `A ${innerR} ${innerR} 0 ${largeArc} 0 ${x1i.toFixed(1)} ${y1i.toFixed(1)}`,
      'Z'
    ].join(' ');

    // Короткое имя спикера для метки
    const shortName = item.name.replace(/^SPEAKER_/, 'S');

    return { path, color, name: shortName, percent: item.percent, labelX, labelY, segmentAngle: effectiveAngle, value: item.value };
  }).filter(Boolean) as Array<{ path: string; color: string; name: string; percent: string; labelX: number; labelY: number; segmentAngle: number; value: number }>;

  // Позиция для отображения общего времени (под радугой)
  const totalLabelY = cy + 10;

  return (
    <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full max-w-md mx-auto my-2">
      <defs>
        <filter id="rainbowGlow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {segments.map((seg, idx) => (
        <g key={idx}>
          {/* Тень для объёма */}
          <path
            d={seg.path}
            fill="rgba(0,0,0,0.08)"
            transform={`translate(0, 2)`}
          />
          {/* Сам сегмент */}
          <path
            d={seg.path}
            fill={seg.color}
            filter="url(#rainbowGlow)"
            className="transition-opacity hover:opacity-80 cursor-default"
          />
          {/* Метка с процентом (только если сегмент достаточно широкий) */}
          {seg.segmentAngle > 0.2 && (
            <text
              x={seg.labelX}
              y={seg.labelY}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="white"
              fontSize="12"
              fontWeight="bold"
              style={{ textShadow: '0 1px 2px rgba(0,0,0,0.3)' }}
            >
              {seg.percent}%
            </text>
          )}
        </g>
      ))}

      {/* Общее время под радугой */}
      <text x={cx} y={totalLabelY} textAnchor="middle" fill="#9CA3AF" fontSize="12">
        Всего
      </text>
      <text x={cx} y={totalLabelY + 16} textAnchor="middle" fill="#374151" className="dark:fill-gray-200" fontSize="16" fontWeight="bold">
        {total.toFixed(0)} сек
      </text>
    </svg>
  );
};