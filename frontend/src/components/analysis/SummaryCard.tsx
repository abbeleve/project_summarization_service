import { Card } from '@/components/ui/Card';
import { type MeetingType } from '@/config/settings';

interface SummaryCardProps {
  title: string;
  summary: string;
  keyPoints: string[];
  meetingType: MeetingType | string;
}

const MEETING_TYPE_COLORS: Record<string, string> = {
  'Оперативное совещание': 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700',
  'Стратегическое совещание': 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700',
  'Финансовое совещание': 'bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700',
  'HR-совещание': 'bg-pink-100 text-pink-800 border-pink-300 dark:bg-pink-900/30 dark:text-pink-300 dark:border-pink-700',
  'Обзор проекта': 'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/30 dark:text-orange-300 dark:border-orange-700',
  'Экстренное совещание': 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700',
};

export const SummaryCard = ({ title, summary, keyPoints, meetingType }: SummaryCardProps) => {
  const badgeClass = MEETING_TYPE_COLORS[meetingType] || 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600';

  return (
    <Card className="space-y-6 p-6 bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
      {/* Заголовок и тип совещания */}
      <div className="flex items-start justify-between">
        <h3 className="text-xl font-bold text-gray-900 dark:text-white">{title}</h3>
        <span className={`px-3 py-1.5 rounded-full text-xs font-medium border ${badgeClass} dark:border-opacity-30`}>
          {meetingType}
        </span>
      </div>

      {/* Краткое содержание - красивая рамка */}
      <div className="border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">📋</span>
          <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-300 uppercase tracking-wide">
            Краткое содержание
          </h4>
        </div>
        <p className="text-blue-900 dark:text-blue-100 leading-relaxed text-sm">
          {summary}
        </p>
      </div>

      {/* Ключевые моменты - тоже в рамке */}
      {keyPoints.length > 0 && (
        <div className="border-l-4 border-amber-500 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">🔑</span>
            <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-300 uppercase tracking-wide">
              Ключевые моменты
            </h4>
          </div>
          <ul className="space-y-2">
            {keyPoints.map((point, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-amber-600 dark:text-amber-400 mt-1 text-lg leading-none flex-shrink-0">•</span>
                <span className="text-amber-900 dark:text-amber-100 text-sm leading-relaxed">{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};