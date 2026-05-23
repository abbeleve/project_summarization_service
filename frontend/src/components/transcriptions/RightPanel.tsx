import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { meetingBotApi } from '@/api/meetingBot';
import { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval, isSameMonth, isToday, addMonths, subMonths } from 'date-fns';
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

  const meetingsByDate: Record<string, number> = {};
  meetings.forEach(m => {
    const dateKey = format(new Date(m.scheduled_at), 'yyyy-MM-dd');
    meetingsByDate[dateKey] = (meetingsByDate[dateKey] || 0) + 1;
  });

  const upcomingMeetings = meetings
    .filter(m => m.status !== 'cancelled' && m.status !== 'failed')
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 10);

  return (
    <div className="w-[320px] shrink-0 border-l border-gray-200 dark:border-dark-base-700 bg-white dark:bg-dark-base-900 min-h-screen relative z-[1]">
      <div style={{ padding: '16px' }}>
        {/* Calendar */}
        <div className="bg-gray-50 dark:bg-dark-base-800 rounded-2xl p-4 border border-gray-200 dark:border-dark-base-700">
          {/* Month navigation */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <button onClick={() => setCurrentMonth(prev => subMonths(prev, 1))}
              className="w-8 h-8 rounded-lg border-none cursor-pointer bg-transparent text-gray-700 dark:text-gray-300 text-sm">
              ◀
            </button>
            <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
              {format(currentMonth, 'LLLL yyyy', { locale: ru })}
            </span>
            <button onClick={() => setCurrentMonth(prev => addMonths(prev, 1))}
              className="w-8 h-8 rounded-lg border-none cursor-pointer bg-transparent text-gray-700 dark:text-gray-300 text-sm">
              ▶
            </button>
          </div>

          {/* Weekday headers */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', marginBottom: '8px' }}>
            {WEEKDAYS.map(d => (
              <div key={d} className="text-center text-[11px] font-bold text-gray-500 dark:text-dark-base-300 uppercase py-1">
                {d}
              </div>
            ))}
          </div>

          {/* Days grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)' }}>
            {days.map((day, i) => {
              const dateKey = format(day, 'yyyy-MM-dd');
              const hasMeetings = meetingsByDate[dateKey] > 0;
              const inMonth = isSameMonth(day, currentMonth);
              const today = isToday(day);

              return (
                <div key={i}
                  className={`text-center py-1.5 text-[13px] rounded-lg relative
                    ${today ? 'text-white bg-blue-500 font-bold' : ''}
                    ${!inMonth ? 'text-gray-400 dark:text-dark-base-500 font-medium' : ''}
                    ${inMonth && !today ? 'text-gray-900 dark:text-dark-base-100 font-medium' : ''}
                  `}>
                  <span>{format(day, 'd')}</span>
                  {hasMeetings && !today && (
                    <div style={{
                      position: 'absolute', bottom: '1px', left: '50%', transform: 'translateX(-50%)',
                      width: '5px', height: '5px', borderRadius: '50%', background: '#3B82F6'
                    }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Scheduled meetings section */}
        <div style={{ marginTop: '16px' }}>
          <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100 mb-3">
            Запланированные совещания
          </h3>

          {upcomingMeetings.length === 0 ? (
            <div className="text-center py-6 bg-gray-50 dark:bg-dark-base-800 rounded-xl border border-gray-200 dark:border-dark-base-700">
              <p className="text-xs text-gray-400 dark:text-dark-base-400">
                Нет запланированных совещаний
              </p>
              <button onClick={() => navigate('/meeting-bot')}
                className="mt-2 text-xs text-blue-500 border-none bg-transparent cursor-pointer font-medium">
                Запланировать
              </button>
            </div>
          ) : (
            <div>
              {upcomingMeetings.map((meeting) => (
                <div key={meeting.id} onClick={() => navigate('/meeting-bot')}
                  className="flex gap-4 p-4 rounded-xl bg-gray-50 dark:bg-dark-base-800 border border-gray-200 dark:border-dark-base-700 mb-2 cursor-pointer">
                  <div className="w-10 h-10 rounded-xl bg-white dark:bg-dark-base-700 flex items-center justify-center text-lg shrink-0">
                    {PROVIDER_ICONS[meeting.provider] || '📅'}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p className="text-[13px] font-semibold text-gray-900 dark:text-gray-100 truncate">
                      {meeting.bot_name || meeting.meeting_url.replace(/https?:\/\//, '').split('/')[0]}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-dark-base-400 mt-1">
                      {format(new Date(meeting.scheduled_at), 'd MMM, HH:mm', { locale: ru })}
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '6px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: STATUS_DOT_COLORS[meeting.status] || '#9CA3AF', display: 'inline-block' }} />
                      <span className="text-xs text-gray-500 dark:text-dark-base-300 font-medium">
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
    </div>
  );
};
