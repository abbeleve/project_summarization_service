import { PieChart, Pie, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { Card } from '@/components/ui/Card';
import { type TranscriptSegment } from '@/types/transcript';

interface SpeakerDistributionChartProps {
  segments: TranscriptSegment[];
}

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

export const SpeakerDistributionChart = ({ segments }: SpeakerDistributionChartProps) => {
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
    data.push({
      name,
      value,
      fill: COLORS[idx % COLORS.length],
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
      <Card className="p-6 text-center text-gray-500">
        Нет данных о спикерах
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-4">🗣️ Распределение времени по спикерам</h4>
      
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
              // label={({ name, percent }) => {
              //   const displayPercent = percent !== undefined && percent > 0
              //     ? (percent * 100).toFixed(1)
              //     : '0';
              //   return `${name} ${displayPercent}%`;
              // }}
              // labelLine={false}
            >
            </Pie>
            <Tooltip 
              formatter={(value: number | undefined) => `${value?.toFixed(1)} сек`}
              labelFormatter={(label) => `Спикер: ${label}`}
            />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Table view */}
      <div className="mt-4">
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
              <tr key={idx} className="border-t">
                <td className="py-2 flex items-center gap-2">
                  <span 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: item.fill }}
                  />
                  {item.name}
                </td>
                <td className="py-2 text-right">{item.value.toFixed(1)} сек</td>
                <td className="py-2 text-right">{((item.value / total) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};