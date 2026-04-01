import { Card } from '@/components/ui/Card';
import { type MeetingType } from '@/config/settings';

interface SummaryCardProps {
  title: string;
  summary: string;
  keyPoints: string[];
  meetingType: MeetingType | string;
}

const MEETING_TYPE_COLORS: Record<string, string> = {
  'Оперативное совещание': 'bg-blue-100 text-blue-800 border-blue-300',
  'Стратегическое совещание': 'bg-purple-100 text-purple-800 border-purple-300',
  'Финансовое совещание': 'bg-green-100 text-green-800 border-green-300',
  'HR-совещание': 'bg-pink-100 text-pink-800 border-pink-300',
  'Обзор проекта': 'bg-orange-100 text-orange-800 border-orange-300',
  'Экстренное совещание': 'bg-red-100 text-red-800 border-red-300',
};

export const SummaryCard = ({ title, summary, keyPoints, meetingType }: SummaryCardProps) => {
  const badgeClass = MEETING_TYPE_COLORS[meetingType] || 'bg-gray-100 text-gray-800 border-gray-300';

  return (
    <Card className="space-y-6 p-6">
      {/* Заголовок и тип совещания */}
      <div className="flex items-start justify-between">
        <h3 className="text-xl font-bold text-gray-900">{title}</h3>
        <span className={`px-3 py-1.5 rounded-full text-xs font-medium border ${badgeClass}`}>
          {meetingType}
        </span>
      </div>

      {/* Краткое содержание - красивая рамка */}
      <div className="border-l-4 border-blue-500 bg-blue-50 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">📋</span>
          <h4 className="text-sm font-semibold text-blue-900 uppercase tracking-wide">
            Краткое содержание
          </h4>
        </div>
        <p className="text-blue-900 leading-relaxed text-sm">
          {summary}
        </p>
      </div>

      {/* Ключевые моменты - тоже в рамке */}
      {keyPoints.length > 0 && (
        <div className="border-l-4 border-amber-500 bg-amber-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">🔑</span>
            <h4 className="text-sm font-semibold text-amber-900 uppercase tracking-wide">
              Ключевые моменты
            </h4>
          </div>
          <ul className="space-y-2">
            {keyPoints.map((point, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-amber-600 text-lg leading-none flex-shrink-0">•</span>
                <span className="text-amber-900 text-sm leading-relaxed">{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};