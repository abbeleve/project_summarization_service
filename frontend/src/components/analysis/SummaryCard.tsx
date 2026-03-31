import { Card } from '@/components/ui/Card';
import { type MeetingType } from '@/config/settings';

interface SummaryCardProps {
  title: string;
  summary: string;
  keyPoints: string[];
  meetingType: MeetingType | string;
}

const MEETING_TYPE_COLORS: Record<string, string> = {
  'Оперативное совещание': 'bg-blue-100 text-blue-800',
  'Стратегическое совещание': 'bg-purple-100 text-purple-800',
  'Финансовое совещание': 'bg-green-100 text-green-800',
  'HR-совещание': 'bg-pink-100 text-pink-800',
  'Обзор проекта': 'bg-orange-100 text-orange-800',
  'Экстренное совещание': 'bg-red-100 text-red-800',
};

export const SummaryCard = ({ title, summary, keyPoints, meetingType }: SummaryCardProps) => {
  const badgeClass = MEETING_TYPE_COLORS[meetingType] || 'bg-gray-100 text-gray-800';

  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${badgeClass}`}>
          {meetingType}
        </span>
      </div>
      
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-2">📋 Краткое содержание</h4>
        <p className="text-gray-600 leading-relaxed">{summary}</p>
      </div>

      {keyPoints.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">🔑 Ключевые моменты</h4>
          <ul className="space-y-2">
            {keyPoints.map((point, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-primary-600 mt-1">•</span>
                <span className="text-gray-600">{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};