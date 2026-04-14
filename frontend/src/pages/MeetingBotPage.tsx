import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { meetingBotApi, type ScheduledMeeting, type JoinMeetingPayload, type ScheduleMeetingPayload } from "@/api/meetingBot";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import {
  TRANSCRIBE_CONFIG,
  DIARIZATION_CONFIG,
  LLM_MODELS,
  DEFAULT_SETTINGS,
} from "@/config/settings";
import { format } from "date-fns";
import { ru } from "date-fns/locale";
import { useActiveTasks } from "@/hooks/useActiveTasks";

type MeetingMode = "join" | "schedule";

interface ModelSettings {
  transcribe_model: string;
  diarization_model: string;
  diarize_lib: string;
  transcribe_lib: string;
  llm_model: string;
  noise_suppression: boolean;
}

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
  { value: "google", label: "Google Meet", icon: "📹" },
  { value: "microsoft", label: "Microsoft Teams", icon: "🏢" },
  { value: "zoom", label: "Zoom", icon: "🎥" },
] as const;

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  processing: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  recording: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
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

export default function MeetingBotPage() {
  const queryClient = useQueryClient();

  // Form state
  const [mode, setMode] = useState<MeetingMode>("join");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [provider, setProvider] = useState<string>("google");
  const [botName, setBotName] = useState("Meeting Notetaker");
  const [scheduledAt, setScheduledAt] = useState("");

  // Custom date picker state (replaces datetime-local)
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [scheduleTimezone, setScheduleTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow");

  const [showModels, setShowModels] = useState(false);
  const [settings, setSettings] = useState<ModelSettings>({
    transcribe_model: DEFAULT_SETTINGS.transcribeModel,
    diarization_model: DEFAULT_SETTINGS.diarizationModel,
    diarize_lib: DEFAULT_SETTINGS.diarizeLib,
    transcribe_lib: DEFAULT_SETTINGS.transcribeLib,
    llm_model: DEFAULT_SETTINGS.llmModel,
    noise_suppression: DEFAULT_SETTINGS.noiseSuppression,
  });

  // Form errors
  const [formError, setFormError] = useState<string | null>(null);

  // Join meeting mutation
  const joinMutation = useMutation({
    mutationFn: (payload: JoinMeetingPayload) => meetingBotApi.joinMeeting(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      setFormError(null);
      setMeetingUrl("");
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
      bot_name: botName || "Meeting Notetaker",
      ...settings,
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
  }, [meetingUrl, provider, botName, settings, mode, computeScheduledAt, joinMutation, scheduleMutation]);

  const handleCancel = useCallback((id: string) => {
    cancelMutation.mutate(id);
  }, [cancelMutation]);

  const isProcessing = joinMutation.isPending || scheduleMutation.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section>
        <div className="flex items-center gap-4 mb-2">
          <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg">
            <span className="text-2xl">🤖</span>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Meeting Bot
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Автоматическое подключение к совещаниям
            </p>
          </div>
        </div>
      </section>

      {/* Mode Toggle */}
      <Card>
        <div className="flex gap-2">
          <button
            onClick={() => setMode("join")}
            className={`flex-1 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
              mode === "join"
                ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            }`}
          >
            ⚡ Подключиться сейчас
          </button>
          <button
            onClick={() => setMode("schedule")}
            className={`flex-1 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
              mode === "schedule"
                ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            }`}
          >
            📅 Запланировать
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
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
            />
          </div>

          {/* Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Платформа
            </label>
            <div className="grid grid-cols-3 gap-3">
              {PROVIDER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleProviderChange(opt.value)}
                  className={`flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-all ${
                    provider === opt.value
                      ? "border-violet-500 bg-violet-50 dark:bg-violet-900/30"
                      : "border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500"
                  }`}
                >
                  <span className="text-2xl">{opt.icon}</span>
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    {opt.label}
                  </span>
                </button>
              ))}
            </div>
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
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
            />
          </div>

          {/* Scheduled Time — Custom Date Picker */}
          {mode === "schedule" && (
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Время начала
              </label>

              {/* Date + Time row */}
              <div className="flex gap-3">
                {/* Date input — displays as "День Месяц Год" */}
                <div className="flex-1 relative">
                  <input
                    type="date"
                    value={scheduleDate}
                    onChange={(e) => setScheduleDate(e.target.value)}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  />
                  {/* Display formatted date overlay */}
                  {scheduleDate && (
                    <div className="mt-1 text-xs text-violet-600 dark:text-violet-400 font-medium">
                      {format(new Date(scheduleDate + "T00:00:00"), "dd MMM yyyy", { locale: ru })}
                    </div>
                  )}
                </div>

                {/* Time input — custom 24-hour selects (no AM/PM) */}
                <div className="flex items-center gap-1 w-36">
                  <select
                    value={scheduleTime ? scheduleTime.split(":")[0] : ""}
                    onChange={(e) => {
                      const h = e.target.value;
                      const m = scheduleTime ? scheduleTime.split(":")[1] || "00" : "00";
                      setScheduleTime(`${h}:${m}`);
                    }}
                    className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center text-base font-mono focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  >
                    <option value="" disabled>ЧЧ</option>
                    {Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, "0")).map((h) => (
                      <option key={h} value={h} className="dark:bg-gray-700 dark:text-white">{h}</option>
                    ))}
                  </select>
                  <span className="text-gray-500 font-mono text-lg">:</span>
                  <select
                    value={scheduleTime ? scheduleTime.split(":")[1] : ""}
                    onChange={(e) => {
                      const m = e.target.value;
                      const h = scheduleTime ? scheduleTime.split(":")[0] || "00" : "00";
                      setScheduleTime(`${h}:${m}`);
                    }}
                    className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center text-base font-mono focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  >
                    <option value="" disabled>ММ</option>
                    {Array.from({ length: 60 }, (_, i) => i.toString().padStart(2, "0")).map((m) => (
                      <option key={m} value={m} className="dark:bg-gray-700 dark:text-white">{m}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Timezone selector */}
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                  Часовой пояс
                </label>
                <select
                  value={scheduleTimezone}
                  onChange={(e) => setScheduleTimezone(e.target.value)}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                >
                  {TIMEZONE_OPTIONS.map((tz) => (
                    <option key={tz.value} value={tz.value} className="dark:bg-gray-700 dark:text-white">
                      {tz.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Preview of computed ISO */}
              {scheduleDate && scheduleTime && (
                <div className="text-xs text-gray-400 dark:text-gray-500 font-mono bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2">
                  {computeScheduledAt() || "—"}
                </div>
              )}
            </div>
          )}

          {/* Model Selection Accordion */}
          <details
            open={showModels}
            onToggle={(e) => setShowModels((e.target as HTMLDetailsElement).open)}
            className="group border border-gray-200 dark:border-gray-700 rounded-2xl overflow-visible bg-white dark:bg-gray-800"
          >
            <summary className="flex items-center gap-3 font-semibold cursor-pointer p-4 bg-gradient-to-r from-slate-50 to-gray-50 dark:from-gray-700 dark:to-gray-800 hover:from-slate-100 hover:to-gray-100 dark:hover:from-gray-600 dark:hover:to-gray-700 transition-colors list-none">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-400 to-gray-500 flex items-center justify-center shadow-md">
                <span className="text-lg">⚙️</span>
              </div>
              <span className="text-lg text-gray-900 dark:text-white">Настройки моделей</span>
              <span className="ml-auto text-gray-400 dark:text-gray-500 group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="p-5 space-y-4">
              {/* Информационное сообщение */}
              <div className="bg-gradient-to-r from-rose-50 to-pink-50 dark:from-rose-900/20 dark:to-pink-900/20 border border-rose-200 dark:border-rose-800 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-400 to-pink-500 flex items-center justify-center flex-shrink-0 shadow-sm">
                    <span className="text-lg">💡</span>
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-rose-800 dark:text-rose-300 mb-1">Важная информация</p>
                    <p className="text-sm text-rose-700 dark:text-rose-400 leading-relaxed">
                      Выбирайте модели вручную только в редких случаях: если вас не устраивает результат транскрибации или язык записи отличается от русского.
                      <span className="font-medium"> По умолчанию используются оптимальные настройки.</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Пояснения терминов */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-900/20 dark:to-purple-900/20 border border-violet-200 dark:border-violet-800 rounded-xl p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">📝</span>
                    <span className="font-semibold text-violet-800 dark:text-violet-300 text-sm">Транскрибация</span>
                  </div>
                  <p className="text-xs text-violet-700 dark:text-violet-400 leading-relaxed">
                    Преобразование речи в текст. Модель «слышит» аудио и записывает слова.
                  </p>
                </div>
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">👥</span>
                    <span className="font-semibold text-blue-800 dark:text-blue-300 text-sm">Диаризация</span>
                  </div>
                  <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">
                    Разделение спикеров. Определяет кто и когда говорил (Спикер 1, Спикер 2 и т.д.).
                  </p>
                </div>
                <div className="bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">🤖</span>
                    <span className="font-semibold text-amber-800 dark:text-amber-300 text-sm">LLM (суммаризация)</span>
                  </div>
                  <p className="text-xs text-amber-700 dark:text-amber-400 leading-relaxed">
                    Нейросеть для создания краткого содержания. Превращает длинный текст в сжатый пересказ.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Транскрибация */}
                <div className="space-y-1">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
                    <span className="w-1 h-4 bg-violet-500 rounded-full"></span>
                    Библиотека транскрибации
                  </label>
                  <select
                    value={settings.transcribe_lib}
                    onChange={(e) => {
                      const lib = e.target.value;
                      const models = TRANSCRIBE_CONFIG[lib] || [];
                      setSettings((prev) => ({
                        ...prev,
                        transcribe_lib: lib,
                        transcribe_model: models[0] || prev.transcribe_model,
                      }));
                    }}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white dark:bg-gray-700 hover:border-violet-300 dark:hover:border-violet-600"
                  >
                    {Object.keys(TRANSCRIBE_CONFIG).map((lib) => (
                      <option key={lib} value={lib} className="dark:bg-gray-700 dark:text-white">
                        {lib.charAt(0).toUpperCase() + lib.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
                    <span className="w-1 h-4 bg-violet-500 rounded-full"></span>
                    Модель транскрибации
                  </label>
                  <select
                    value={settings.transcribe_model}
                    onChange={(e) => setSettings((prev) => ({ ...prev, transcribe_model: e.target.value }))}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white dark:bg-gray-700 hover:border-violet-300 dark:hover:border-violet-600"
                  >
                    {(TRANSCRIBE_CONFIG[settings.transcribe_lib] || []).map((model) => (
                      <option key={model} value={model} className="dark:bg-gray-700 dark:text-white">{model}</option>
                    ))}
                  </select>
                </div>

                {/* Диаризация */}
                <div className="space-y-1">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
                    <span className="w-1 h-4 bg-blue-500 rounded-full"></span>
                    Библиотека диаризации
                  </label>
                  <select
                    value={settings.diarize_lib}
                    onChange={(e) => {
                      const lib = e.target.value;
                      const models = DIARIZATION_CONFIG[lib] || [];
                      setSettings((prev) => ({
                        ...prev,
                        diarize_lib: lib,
                        diarization_model: models[0] || prev.diarization_model,
                      }));
                    }}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white dark:bg-gray-700 hover:border-violet-300 dark:hover:border-violet-600"
                  >
                    {Object.keys(DIARIZATION_CONFIG).map((lib) => (
                      <option key={lib} value={lib} className="dark:bg-gray-700 dark:text-white">
                        {lib.charAt(0).toUpperCase() + lib.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
                    <span className="w-1 h-4 bg-blue-500 rounded-full"></span>
                    Модель диаризации
                  </label>
                  <select
                    value={settings.diarization_model}
                    onChange={(e) => setSettings((prev) => ({ ...prev, diarization_model: e.target.value }))}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white dark:bg-gray-700 hover:border-violet-300 dark:hover:border-violet-600"
                  >
                    {(DIARIZATION_CONFIG[settings.diarize_lib] || []).map((model) => (
                      <option key={model} value={model} className="dark:bg-gray-700 dark:text-white">{model}</option>
                    ))}
                  </select>
                </div>

                {/* LLM */}
                <div className="space-y-1 md:col-span-2">
                  <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
                    <span className="w-1 h-4 bg-amber-500 rounded-full"></span>
                    Модель LLM
                  </label>
                  <select
                    value={settings.llm_model}
                    onChange={(e) => setSettings((prev) => ({ ...prev, llm_model: e.target.value }))}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-2.5 text-base font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all bg-white dark:bg-gray-700 hover:border-violet-300 dark:hover:border-violet-600"
                  >
                    {LLM_MODELS.map((model) => (
                      <option key={model} value={model} className="dark:bg-gray-700 dark:text-white">{model}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Noise Suppression */}
              <div className="flex items-center gap-3 pt-2">
                <input
                  type="checkbox"
                  id="noise-suppression-meeting"
                  checked={settings.noise_suppression}
                  onChange={(e) => setSettings((prev) => ({ ...prev, noise_suppression: e.target.checked }))}
                  className="w-4 h-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                />
                <label htmlFor="noise-suppression-meeting" className="text-sm text-gray-700 dark:text-gray-300">
                  Подавление шума
                </label>
              </div>
            </div>
          </details>

          {/* Error */}
          {formError && <ErrorMessage message={formError} onRetry={() => setFormError(null)} />}

          {/* Submit Button */}
          <Button
            onClick={handleSubmit}
            isLoading={isProcessing}
            fullWidth
            size="lg"
          >
            {mode === "join" ? "🚀 Подключиться" : "📅 Запланировать"}
          </Button>
        </div>
      </Card>

      {/* Meetings History */}
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <span className="text-lg">📋</span>
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
                className="border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">
                        {meeting.provider === "google" ? "📹" : meeting.provider === "microsoft" ? "🏢" : "🎥"}
                      </span>
                      <span className="font-medium text-gray-900 dark:text-white truncate text-sm">
                        {meeting.meeting_url}
                      </span>
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
                        ⏹ Отозвать бота
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
                          setSettings({
                            transcribe_model: meeting.transcribe_model || DEFAULT_SETTINGS.transcribeModel,
                            diarization_model: meeting.diarization_model || DEFAULT_SETTINGS.diarizationModel,
                            diarize_lib: meeting.diarize_lib || DEFAULT_SETTINGS.diarizeLib,
                            transcribe_lib: meeting.transcribe_lib || DEFAULT_SETTINGS.transcribeLib,
                            llm_model: meeting.llm_model || DEFAULT_SETTINGS.llmModel,
                            noise_suppression: meeting.noise_suppression || false,
                          });
                          setMode("join");
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                      >
                        🔄 Повторить
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
                    className="mt-2 inline-block text-xs text-violet-600 dark:text-violet-400 hover:underline"
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
  );
}
