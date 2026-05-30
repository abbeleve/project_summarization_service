import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { meetingBotApi, type ScheduledMeeting, type JoinMeetingPayload, type ScheduleMeetingPayload } from "@/api/meetingBot";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { DEFAULT_SETTINGS } from "@/config/settings";
import type { ProcessingSettings } from "@/types/transcript";
import { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval, isSameMonth, isToday, addMonths, subMonths } from "date-fns";
import { ru } from "date-fns/locale";
import { useActiveTasks } from "@/hooks/useActiveTasks";

type MeetingMode = "join" | "schedule";

// Load model settings from user's saved preferences (Settings page → localStorage)
const loadMeetingSettings = (): import("@/api/meetingBot").MeetingBotSettings => {
  try {
    const saved = localStorage.getItem("modelSettings");
    if (saved) {
      const s: ProcessingSettings = JSON.parse(saved);
      return {
        transcribe_model: s.transcribeModel,
        diarization_model: s.diarizationModel,
        diarize_lib: s.diarizeLib,
        transcribe_lib: s.transcribeLib,
        llm_model: s.llmModel,
        noise_suppression: s.noiseSuppression,
      };
    }
  } catch {}
  return {
    transcribe_model: DEFAULT_SETTINGS.transcribeModel,
    diarization_model: DEFAULT_SETTINGS.diarizationModel,
    diarize_lib: DEFAULT_SETTINGS.diarizeLib,
    transcribe_lib: DEFAULT_SETTINGS.transcribeLib,
    llm_model: DEFAULT_SETTINGS.llmModel,
    noise_suppression: DEFAULT_SETTINGS.noiseSuppression,
  };
};

// Timezone options with common zones
const TIMEZONE_OPTIONS = [
  { value: "Europe/Moscow", label: "Москва (UTC+3)" },
  { value: "Europe/Kaliningrad", label: "Калининград (UTC+2)" },
  { value: "Europe/Samara", label: "Самара (UTC+4)" },
  { value: "Asia/Yekaterinburg", label: "Екатеринбург (UTC+5)" },
  { value: "Asia/Omsk", label: "Омск (UTC+6)" },
  { value: "Asia/Krasnoyarsk", label: "Красноярск (UTC+7)" },
  { value: "Asia/Irkutsk", label: "Иркутск (UTC+8)" },
  { value: "Asia/Yakutsk", label: "Якутск (UTC+9)" },
  { value: "Asia/Vladivostok", label: "Владивосток (UTC+10)" },
  { value: "Asia/Magadan", label: "Магадан (UTC+11)" },
  { value: "Asia/Kamchatka", label: "Камчатка (UTC+12)" },
  { value: "UTC", label: "UTC" },
  { value: "Europe/London", label: "Лондон (UTC+0/+1)" },
  { value: "Europe/Berlin", label: "Берлин (UTC+1/+2)" },
  { value: "America/New_York", label: "Нью-Йорк (UTC-5/-4)" },
  { value: "America/Chicago", label: "Чикаго (UTC-6/-5)" },
  { value: "America/Denver", label: "Денвер (UTC-7/-6)" },
  { value: "America/Los_Angeles", label: "Лос-Анджелес (UTC-8/-7)" },
  { value: "Asia/Shanghai", label: "Шанхай (UTC+8)" },
  { value: "Asia/Tokyo", label: "Токио (UTC+9)" },
  { value: "Asia/Dubai", label: "Дубай (UTC+4)" },
  { value: "Asia/Kolkata", label: "Индия (UTC+5:30)" },
];

const PROVIDER_OPTIONS = [
  { value: "google", label: "Google Meet", icon: "/images/Google_Meet_Logo.svg" },
  { value: "microsoft", label: "Microsoft Teams", icon: "/images/Microsoft_Teams.png" },
  { value: "zoom", label: "Zoom", icon: "/images/zoom.png" },
] as const;

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  processing: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  recording: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-gray-100 text-gray-700 dark:bg-dark-base-700 dark:text-gray-300",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Ожидание",
  processing: "Подключение",
  recording: "Запись",
  completed: "Завершено",
  failed: "Ошибка",
  cancelled: "Отменено",
};

const PROVIDER_LABELS: Record<string, string> = {
  google: "Google Meet",
  microsoft: "Microsoft Teams",
  zoom: "Zoom",
};

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export default function MeetingBotPage() {
  const queryClient = useQueryClient();

  // Form state
  const [mode, setMode] = useState<MeetingMode>("join");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [provider, setProvider] = useState<string>("google");
  const [meetingTitle, setMeetingTitle] = useState("");
  const [botName, setBotName] = useState("Meeting Notetaker");
  const [scheduledAt, setScheduledAt] = useState("");

  // Custom date picker state (replaces datetime-local)
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [scheduleTimezone, setScheduleTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow");

  // Calendar month navigation
  const [calendarMonth, setCalendarMonth] = useState(new Date());

  // Form errors
  const [formError, setFormError] = useState<string | null>(null);

  // Join meeting mutation
  const joinMutation = useMutation({
    mutationFn: (payload: JoinMeetingPayload) => meetingBotApi.joinMeeting(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      setFormError(null);
      setMeetingUrl("");
      setMeetingTitle("");
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || "Ошибка при подключении к совещанию");
    },
  });

  // Schedule meeting mutation
  const scheduleMutation = useMutation({
    mutationFn: (payload: ScheduleMeetingPayload) => meetingBotApi.scheduleMeeting(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      setFormError(null);
      setMeetingUrl("");
      setMeetingTitle("");
      setScheduledAt("");
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || "Ошибка при планировании совещания");
    },
  });

  // Cancel meeting mutation
  const cancelMutation = useMutation({
    mutationFn: (id: string) => meetingBotApi.cancelMeeting(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });

  // Delete meeting permanently mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => meetingBotApi.deleteMeetingPermanently(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });

  // Fetch meetings
  const { data: meetingsData, isLoading: meetingsLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => meetingBotApi.getMeetings(100),
    refetchInterval: 15000, // Poll every 15s
  });

  // Auto-discover ML tasks from meetings and add to active tasks tracker
  // so HomePage can show transcription progress
  const { addTask } = useActiveTasks();
  useEffect(() => {
    const meetings = meetingsData?.data?.meetings || [];
    for (const meeting of meetings) {
      if (meeting.ml_task_id) {
        addTask(meeting.ml_task_id);
      }
    }
  }, [meetingsData, addTask]);

  const handleProviderChange = useCallback((value: string) => {
    setProvider(value);
  }, []);

  // Compute scheduledAt ISO string from date, time, and timezone
  const computeScheduledAt = useCallback((): string | null => {
    if (!scheduleDate || !scheduleTime || !scheduleTimezone) return null;
    // Use Intl to convert local date/time in selected timezone to ISO string
    // Parse the date and time as if they're in the selected timezone
    const dateTimeStr = `${scheduleDate}T${scheduleTime}`;
    // Use a library-free approach: create date in UTC, then adjust by timezone offset
    const tzDate = new Date(dateTimeStr);
    // Get the offset of the selected timezone at that date
    try {
      const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: scheduleTimezone,
        year: 'numeric', month: 'numeric', day: 'numeric',
        hour: 'numeric', minute: 'numeric', second: 'numeric',
        hour12: false,
      });
      const parts = formatter.formatToParts(tzDate);
      const getPart = (type: string) => parts.find(p => p.type === type)?.value || '';
      const year = getPart('year');
      const month = getPart('month').padStart(2, '0');
      const day = getPart('day').padStart(2, '0');
      const hour = getPart('hour').padStart(2, '0');
      const minute = getPart('minute').padStart(2, '0');
      const second = getPart('second').padStart(2, '0');

      // Create date in the target timezone
      const targetDate = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}`);

      // Calculate timezone offset in minutes
      const utcDate = new Date(targetDate.toUTCString());
      const localDate = new Date(targetDate.toLocaleString('en-US', { timeZone: scheduleTimezone }));
      const offsetMs = localDate.getTime() - utcDate.getTime();
      const offsetMin = offsetMs / (1000 * 60);

      // Format offset as +HH:MM or -HH:MM
      const sign = offsetMin >= 0 ? '+' : '-';
      const absOffset = Math.abs(offsetMin);
      const offsetHours = Math.floor(absOffset / 60).toString().padStart(2, '0');
      const offsetMinutes = (absOffset % 60).toString().padStart(2, '0');

      return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${offsetHours}:${offsetMinutes}`;
    } catch {
      // Fallback: treat as local time
      return `${scheduleDate}T${scheduleTime}`;
    }
  }, [scheduleDate, scheduleTime, scheduleTimezone]);

  // Keep scheduledAt in sync with custom date picker
  useEffect(() => {
    if (mode === "schedule") {
      const iso = computeScheduledAt();
      setScheduledAt(iso || "");
    }
  }, [scheduleDate, scheduleTime, scheduleTimezone, mode, computeScheduledAt]);

  const handleSubmit = useCallback(() => {
    setFormError(null);

    if (!meetingUrl.trim()) {
      setFormError("Введите ссылку на совещание");
      return;
    }

    if (mode === "schedule") {
      const iso = computeScheduledAt();
      if (!iso) {
        setFormError("Укажите дату и время начала совещания");
        return;
      }
      const scheduledDateObj = new Date(iso);
      if (scheduledDateObj <= new Date()) {
        setFormError("Время должно быть в будущем");
        return;
      }
    }

    const basePayload = {
      meeting_url: meetingUrl.trim(),
      provider,
      title: meetingTitle.trim() || undefined,
      bot_name: botName || "Meeting Notetaker",
      ...loadMeetingSettings(),
    };

    if (mode === "join") {
      joinMutation.mutate(basePayload as JoinMeetingPayload);
    } else {
      const iso = computeScheduledAt();
      scheduleMutation.mutate({
        ...basePayload,
        scheduled_at: iso || "",
      } as ScheduleMeetingPayload);
    }
  }, [meetingUrl, provider, botName, mode, computeScheduledAt, joinMutation, scheduleMutation]);

  const handleCancel = useCallback((id: string) => {
    cancelMutation.mutate(id);
  }, [cancelMutation]);

  const isProcessing = joinMutation.isPending || scheduleMutation.isPending;

  return (
    <div className="bg-gray-50 dark:bg-[rgb(35,35,38)] min-h-screen">
      <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <section className="pt-8">
        <div>
          <h1 className="text-5xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight">
            Meeting Bot
          </h1>
          <p className="text-base text-gray-500 dark:text-gray-300 mt-2 leading-relaxed">
            Автоматическое подключение к совещаниям.
          </p>
          <p className="text-base text-gray-500 dark:text-gray-300 mt-2 leading-relaxed">
            Введите ссылку на совещание и отправьте бота чтобы он сделал все за вас!
          </p>
        </div>
      </section>

      {/* Mode Toggle */}
      <Card>
        <div className="flex gap-3">
          <button
            onClick={() => setMode("join")}
            className={`flex-1 px-6 py-3 rounded-xl font-semibold text-base transition-colors ${
              mode === "join"
                ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white"
                : "bg-gray-100 dark:bg-dark-base-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-base-600"
            }`}
          >
            Подключиться сейчас
          </button>
          <button
            onClick={() => setMode("schedule")}
            className={`flex-1 px-6 py-3 rounded-xl font-semibold text-base transition-colors ${
              mode === "schedule"
                ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white"
                : "bg-gray-100 dark:bg-dark-base-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-base-600"
            }`}
          >
            Запланировать
          </button>
        </div>
      </Card>

      {/* Form */}
      <Card>
        <div className="space-y-4">
          {/* Meeting URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Ссылка на совещание
            </label>
            <input
              type="url"
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              placeholder="https://meet.google.com/abc-defg-hij"
              className="w-full border border-gray-300 dark:border-dark-base-600 rounded-lg px-4 py-2 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Платформа
            </label>
            <div className="grid grid-cols-3 gap-4">
              {PROVIDER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleProviderChange(opt.value)}
                  className={`flex flex-col items-center gap-4 py-8 px-4 rounded-xl border-2 transition-all ${
                    provider === opt.value
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-900/30"
                      : "border-gray-200 dark:border-dark-base-600 hover:border-gray-300 dark:hover:border-dark-base-500"
                  }`}
                >
                  <img
                    src={opt.icon}
                    alt={opt.label}
                    className="w-20 h-20 object-contain"
                  />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {opt.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Bot Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Название совещания
            </label>
            <input
              type="text"
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
              placeholder="Например: Еженедельный синк"
              className="w-full border border-gray-300 dark:border-dark-base-600 rounded-lg px-4 py-2 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Bot Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Имя бота
            </label>
            <input
              type="text"
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
              placeholder="Meeting Notetaker"
              className="w-full border border-gray-300 dark:border-dark-base-600 rounded-lg px-4 py-2 bg-white dark:bg-dark-base-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-dark-base-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Schedule — visual calendar + clock face */}
          {mode === "schedule" && (() => {
            const monthStart = startOfMonth(calendarMonth);
            const monthEnd = endOfMonth(calendarMonth);
            const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
            const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
            const days = eachDayOfInterval({ start: calStart, end: calEnd });

            return (
            <div className="space-y-4 py-4 border-t border-gray-200 dark:border-dark-base-700 pt-6">
              {/* Date/time summary bar */}
              <div className="text-center py-2">
                <div className="text-lg text-gray-900 dark:text-gray-100 flex items-center justify-center gap-2 flex-wrap">
                  <span>Бот подключится:</span>
                  <input
                    type="date"
                    value={scheduleDate}
                    onChange={(e) => setScheduleDate(e.target.value)}
                    className="bg-transparent border-b border-gray-400 dark:border-gray-500 text-blue-600 dark:text-blue-400 font-bold text-lg px-1 py-0.5 outline-none cursor-pointer w-[180px] text-center"
                  />
                  <span>в</span>
                  <input
                    type="text"
                    value={scheduleTime}
                    onChange={(e) => {
                      const val = e.target.value.replace(/[^0-9:]/g, "").slice(0, 5);
                      setScheduleTime(val);
                    }}
                    placeholder="ЧЧ:ММ"
                    className="bg-transparent border-b border-gray-400 dark:border-gray-500 text-blue-600 dark:text-blue-400 font-bold text-lg px-1 py-0.5 outline-none w-16 text-center"
                  />
                  <select value={scheduleTimezone} onChange={(e) => setScheduleTimezone(e.target.value)}
                    className="bg-transparent border-b border-gray-400 dark:border-gray-500 text-sm text-gray-500 dark:text-gray-400 outline-none cursor-pointer appearance-none px-1"
                  >
                    {TIMEZONE_OPTIONS.map((tz) => (
                      <option key={tz.value} value={tz.value} className="dark:bg-dark-base-800 dark:text-white">{tz.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-start justify-center gap-10">
                {/* Calendar widget — left */}
                <div className="bg-gray-50 dark:bg-dark-base-800 rounded-2xl p-5 border border-gray-200 dark:border-dark-base-700 w-[340px]">
                  <div className="flex items-center justify-between mb-3">
                    <button onClick={() => setCalendarMonth(prev => subMonths(prev, 1))}
                      className="w-8 h-8 rounded-lg bg-transparent text-gray-700 dark:text-gray-300 text-sm hover:bg-gray-200 dark:hover:bg-dark-base-700 transition-colors cursor-pointer"
                    >◀</button>
                    <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                      {format(calendarMonth, "LLLL yyyy", { locale: ru })}
                    </span>
                    <button onClick={() => setCalendarMonth(prev => addMonths(prev, 1))}
                      className="w-8 h-8 rounded-lg bg-transparent text-gray-700 dark:text-gray-300 text-sm hover:bg-gray-200 dark:hover:bg-dark-base-700 transition-colors cursor-pointer"
                    >▶</button>
                  </div>
                  <div className="grid grid-cols-7 mb-2">
                    {WEEKDAYS.map(d => (
                      <div key={d} className="text-center text-[11px] font-bold text-gray-500 dark:text-dark-base-300 uppercase py-1">{d}</div>
                    ))}
                  </div>
                  <div className="grid grid-cols-7">
                    {days.map((day, i) => {
                      const dateKey = format(day, "yyyy-MM-dd");
                      const selected = dateKey === scheduleDate;
                      const inMonth = isSameMonth(day, calendarMonth);
                      const today = isToday(day);
                      return (
                        <button key={i} onClick={() => setScheduleDate(dateKey)}
                          className={`text-center py-1.5 text-[13px] rounded-lg relative cursor-pointer transition-colors
                            ${selected ? "bg-blue-500 text-white font-bold" : ""}
                            ${!selected && today ? "text-blue-600 font-bold" : ""}
                            ${!inMonth && !selected ? "text-gray-400 dark:text-dark-base-500" : ""}
                            ${inMonth && !selected && !today ? "text-gray-900 dark:text-dark-base-100 hover:bg-gray-200 dark:hover:bg-dark-base-700" : ""}
                          `}
                        >{format(day, "d")}</button>
                      );
                    })}
                  </div>
                </div>

                {/* Analog clock faces — right */}
                <div className="flex items-start gap-6">
                  {/* Hours clock face */}
                  <div className="flex flex-col items-center">
                    <span className="text-xs font-semibold text-gray-500 dark:text-dark-base-400 mb-2">Часы</span>
                    <div className="relative w-64 h-64 rounded-full bg-gray-50 dark:bg-dark-base-800 border-4 border-gray-200 dark:border-dark-base-700 shadow-inner">
                      {/* Center dot */}
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-blue-500 z-10 shadow" />

                      {/* Hour numbers 1–12 in a circle */}
                      {(() => {
                        const currentH = scheduleTime ? parseInt(scheduleTime.split(":")[0]) : 0;
                        const currentM = scheduleTime ? parseInt(scheduleTime.split(":")[1]) : 0;
                        const hourAngle = ((currentH % 12) * 30) + (currentM * 0.5);

                        return (<>
                      {Array.from({ length: 12 }, (_, i) => {
                        const angle = (i * 30 - 90) * Math.PI / 180;
                        const r = 100;
                        const cx = 128, cy = 128;
                        const x = cx + r * Math.cos(angle) - 16;
                        const y = cy + r * Math.sin(angle) - 16;
                        const hourNum = i === 0 ? 12 : i;
                        const displayHour = currentH % 12 || 12;
                        const selected = displayHour === hourNum;
                        const hour12 = hourNum === 12 ? 0 : hourNum;

                        return (
                          <button key={i} onClick={() => {
                            const m = scheduleTime ? scheduleTime.split(":")[1] || "00" : "00";
                            const isPM = currentH >= 12;
                            const h = isPM ? hour12 + 12 : hour12;
                            setScheduleTime(`${h.toString().padStart(2, "0")}:${m}`);
                          }}
                            className={`absolute w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors cursor-pointer
                              ${selected ? "bg-blue-500 text-white shadow-md" : "text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-base-700"}
                            `}
                            style={{ left: x, top: y }}
                          >{hourNum}</button>
                        );
                      })}

                      {/* Hour hand */}
                      <div className="absolute top-1/2 left-1/2 z-[5]" style={{
                        transform: `translate(-50%, -100%) rotate(${hourAngle}deg)`,
                        transformOrigin: 'center bottom',
                      }}>
                        <div className="w-[5px] h-[50px] bg-gray-800 dark:bg-gray-200 rounded-full" />
                      </div>
                      </>);
                      })()}
                    </div>
                  </div>

                  {/* Minutes clock face */}
                  <div className="flex flex-col items-center">
                    <span className="text-xs font-semibold text-gray-500 dark:text-dark-base-400 mb-2">Минуты</span>
                    <div className="relative w-64 h-64 rounded-full bg-gray-50 dark:bg-dark-base-800 border-4 border-gray-200 dark:border-dark-base-700 shadow-inner">
                      {/* Minute numbers 00, 05, 10...55 in a circle */}
                      {(() => {
                        const currentM = scheduleTime ? parseInt(scheduleTime.split(":")[1]) : 0;
                        const minuteAngle = currentM * 6;

                        return (<>
                      {Array.from({ length: 12 }, (_, i) => {
                        const angle = (i * 30 - 90) * Math.PI / 180;
                        const r = 100;
                        const cx = 128, cy = 128;
                        const x = cx + r * Math.cos(angle) - 14;
                        const y = cy + r * Math.sin(angle) - 14;
                        const minuteVal = (i * 5).toString().padStart(2, "0");
                        const selected = currentM === i * 5;

                        return (
                          <button key={i} onClick={() => {
                            const h = scheduleTime ? scheduleTime.split(":")[0] || "00" : "00";
                            setScheduleTime(`${h}:${minuteVal}`);
                          }}
                            className={`absolute w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-colors cursor-pointer
                              ${selected ? "bg-blue-500 text-white shadow-md" : "text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-base-700"}
                            `}
                            style={{ left: x, top: y }}
                          >{minuteVal}</button>
                        );
                      })}

                      {/* Minute hand */}
                      <div className="absolute top-1/2 left-1/2 z-[5]" style={{
                        transform: `translate(-50%, -100%) rotate(${minuteAngle}deg)`,
                        transformOrigin: 'center bottom',
                      }}>
                        <div className="w-[3px] h-[65px] bg-blue-500 dark:bg-blue-400 rounded-full" />
                      </div>
                      </>);
                      })()}
                    </div>
                  </div>
                </div>
              </div>

              {scheduleDate && scheduleTime && (
                <div className="text-center">
                  <div className="inline-block text-sm text-gray-400 dark:text-gray-500 font-mono bg-gray-50 dark:bg-dark-base-800 rounded-xl px-4 py-2">
                    {computeScheduledAt() || "—"}
                  </div>
                </div>
              )}
            </div>
            );
          })()}

          {/* Error */}
          {formError && <ErrorMessage message={formError} onRetry={() => setFormError(null)} />}

          {/* Submit Button */}
          <Button
            onClick={handleSubmit}
            isLoading={isProcessing}
            fullWidth
            size="lg"
          >
            {mode === "join" ? "Подключиться" : "Запланировать"}
          </Button>
        </div>
      </Card>

      {/* Meetings History */}
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          История совещаний
        </h2>

        {meetingsLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner size="md" text="Загрузка..." />
          </div>
        ) : !meetingsData?.data?.meetings?.length ? (
          <p className="text-center text-gray-500 dark:text-gray-400 py-8">
            Нет запланированных совещаний
          </p>
        ) : (
          <div className="space-y-3">
            {meetingsData.data.meetings.map((meeting: ScheduledMeeting) => (
              <div
                key={meeting.id}
                className="border border-gray-200 dark:border-dark-base-700 rounded-xl p-4 hover:bg-gray-50 dark:hover:bg-dark-base-750 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">
                        {meeting.provider === "google" ? "📹" : meeting.provider === "microsoft" ? "🏢" : "🎥"}
                      </span>
                      <span className="font-semibold text-gray-900 dark:text-white truncate text-sm">
                        {meeting.title || meeting.meeting_url}
                      </span>
                      {meeting.title && (
                        <span className="text-xs text-gray-400 dark:text-gray-500 truncate hidden sm:inline">
                          {meeting.meeting_url}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                      <span>{PROVIDER_LABELS[meeting.provider] || meeting.provider}</span>
                      <span>•</span>
                      <span className="font-medium">
                        {format(new Date(meeting.scheduled_at), "dd MMM yyyy, HH:mm", { locale: ru })}
                      </span>
                      <span className="text-gray-400">
                        {(() => {
                          try {
                            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
                            const abbr = new Date(meeting.scheduled_at)
                              .toLocaleTimeString('en-US', { timeZone: tz, timeZoneName: 'short' })
                              .split(' ')
                              .pop();
                            return abbr || '';
                          } catch {
                            return '';
                          }
                        })()}
                      </span>
                      <span>•</span>
                      <span>
                        {meeting.transcribe_lib}/{meeting.transcribe_model}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[meeting.status]}`}
                    >
                      {STATUS_LABELS[meeting.status] || meeting.status}
                    </span>
                    {(meeting.status === "pending" || meeting.status === "processing") && (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => handleCancel(meeting.id)}
                        isLoading={cancelMutation.isPending}
                      >
                        Отменить
                      </Button>
                    )}
                    {meeting.status === "recording" && (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => {
                          if (window.confirm("Отозвать бота из конференции?")) {
                            handleCancel(meeting.id);
                          }
                        }}
                        isLoading={cancelMutation.isPending}
                      >
                        Отозвать бота
                      </Button>
                    )}
                    {meeting.status === "failed" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          // Re-use the join form with the same data
                          setMeetingUrl(meeting.meeting_url);
                          setProvider(meeting.provider as any);
                          setBotName(meeting.bot_name);
                          setMode("join");
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                      >
                        Повторить
                      </Button>
                    )}

                    {/* Delete button for completed/cancelled/failed meetings */}
                    {(meeting.status === "completed" || meeting.status === "cancelled" || meeting.status === "failed") && (
                      <button
                        onClick={() => {
                          if (window.confirm("Удалить запись о совещании?")) {
                            deleteMutation.mutate(meeting.id);
                          }
                        }}
                        className="text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors p-1"
                        title="Удалить"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
                {meeting.error && (
                  <p className="mt-2 text-xs text-red-600 dark:text-red-400">{meeting.error}</p>
                )}
                {meeting.result_transcript_id && (
                  <a
                    href={`/analysis/${meeting.result_transcript_id}`}
                    className="mt-2 inline-block text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    → Открыть анализ
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
      </div>
    </div>
  );
}
