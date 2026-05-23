import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { meetingBotApi } from '@/api/meetingBot';
import { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval, isSameMonth, isSameDay, isToday, addMonths, subMonths } from 'date-fns';
import { ru } from 'date-fns/locale';

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидание',
  processing: 'Подключение',
  recording: 'Запись',
  completed: 'Завершено',
  failed: 'Ошибка',
  cancelled: 'Отменено',
};

const STATUS_DOT_COLORS: Record<string, string> = {
  pending: 'bg-blue-500',
  processing: 'bg-yellow-500',
  recording: 'bg-orange-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-gray-400',
};

const PROVIDER_ICONS: Record<string, string> = {
  google: '📹',
  microsoft: '🏢',
  zoom: '🎥',
};

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

export const RightPanel = () => {
  const navigate = useNavigate();
  const [currentMonth, setCurrentMonth] = useState(new Date());

  const { data: meetingsData } = useQuery({
    queryKey: ['scheduled-meetings'],
    queryFn: () => meetingBotApi.getMeetings(50),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const meetings = meetingsData?.data?.meetings || [];

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calendarStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calendarEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });

  const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd });

  const prevMonth = () => setCurrentMonth(prev => subMonths(prev, 1));
  const nextMonth = () => setCurrentMonth(prev => addMonths(prev, 1));

  // Group meetings by date for calendar dots
  const meetingsByDate: Record<string, number> = {};
  meetings.forEach(m => {
    const dateKey = format(new Date(m.scheduled_at), 'yyyy-MM-dd');
    meetingsByDate[dateKey] = (meetingsByDate[dateKey] || 0) + 1;
  });

  // Future/pending meetings sorted by date
  const now = new Date();
  const upcomingMeetings = meetings
    .filter(m => m.status !== 'cancelled' && m.status !== 'failed')
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 10);

  return (
    <aside className="w-[320px] flex-shrink-0 border-l border-gray-200 dark:border-dark-base-700 bg-white dark:bg-dark-base-900 min-h-screen flex flex-col">
      <div className="p-4 flex-1 flex flex-col gap-4">
        {/* Calendar */}
        <div className="bg-gray-50 dark:bg-dark-base-800 rounded-2xl p-4 border border-gray-100 dark:border-dark-base-700">
          {/* Month navigation */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={prevMonth}
              className="w-8 h-8 rounded-lg hover:bg-gray-200 dark:hover:bg-dark-base-700 flex items-center justify-center text-gray-600 dark:text-gray-300 transition-colors cursor-pointer"
            >
              ◀
            </button>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white capitalize">
              {format(currentMonth, 'LLLL yyyy', { locale: ru })}
            </h3>
            <button
              onClick={nextMonth}
              className="w-8 h-8 rounded-lg hover:bg-gray-200 dark:hover:bg-dark-base-700 flex items-center justify-center text-gray-600 dark:text-gray-300 transition-colors cursor-pointer"
            >
              ▶
            </button>
          </div>

          {/* Weekday headers */}
          <div className="grid grid-cols-7 mb-1">
            {WEEKDAYS.map(d => (
              <div key={d} className="text-center text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase py-1">
                {d}
              </div>
            ))}
          </div>

          {/* Days grid */}
          <div className="grid grid-cols-7">
            {days.map((day, i) => {
              const dateKey = format(day, 'yyyy-MM-dd');
              const hasMeetings = meetingsByDate[dateKey] > 0;
              const isCurrentMonth = isSameMonth(day, currentMonth);
              const today = isToday(day);

              return (
                <div
                  key={i}
                  className={`relative text-center py-1.5 text-xs rounded-lg transition-colors ${
                    !isCurrentMonth
                      ? 'text-gray-300 dark:text-dark-base-600'
                      : today
                        ? 'bg-blue-500 text-white font-bold'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-base-700'
                  }`}
                >
                  <span>{format(day, 'd')}</span>
                  {hasMeetings && !today && (
                    <div className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-blue-500" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Scheduled meetings section */}
        <div>
          <h3 className="text-sm font-bold text-gray-900 dark:text-white mb-3">
            Запланированные совещания
          </h3>

          {upcomingMeetings.length === 0 ? (
            <div className="text-center py-6 bg-gray-50 dark:bg-dark-base-800 rounded-xl border border-gray-100 dark:border-dark-base-700">
              <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-dark-base-700 flex items-center justify-center mx-auto mb-2">
                <span className="text-lg">📅</span>
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Нет запланированных совещаний
              </p>
              <button
                onClick={() => navigate('/meeting-bot')}
                className="mt-2 text-xs text-blue-500 hover:text-blue-600 dark:text-blue-400 font-medium transition-colors cursor-pointer"
              >
                Запланировать
              </button>
            </div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {upcomingMeetings.map((meeting) => (
                <div
                  key={meeting.id}
                  onClick={() => navigate('/meeting-bot')}
                  className="flex items-start gap-3 p-3 rounded-xl bg-gray-50 dark:bg-dark-base-800 border border-gray-100 dark:border-dark-base-700 hover:bg-gray-100 dark:hover:bg-dark-base-700 cursor-pointer transition-colors"
                >
                  {/* Provider icon */}
                  <div className="w-8 h-8 rounded-lg bg-white dark:bg-dark-base-700 flex items-center justify-center flex-shrink-0 shadow-sm text-sm">
                    {PROVIDER_ICONS[meeting.provider] || '📅'}
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Title */}
                    <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                      {meeting.bot_name || meeting.meeting_url.replace(/https?:\/\//, '').split('/')[0]}
                    </p>

                    {/* Date & time */}
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className="text-[10px] text-gray-400 dark:text-gray-500">
                        {format(new Date(meeting.scheduled_at), 'd MMM, HH:mm', { locale: ru })}
                      </span>
                    </div>

                    {/* Status */}
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT_COLORS[meeting.status] || 'bg-gray-400'}`} />
                      <span className="text-[10px] text-gray-500 dark:text-gray-400 font-medium">
                        {STATUS_LABELS[meeting.status] || meeting.status}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
