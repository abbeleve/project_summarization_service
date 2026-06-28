import type { ActiveTask } from '@/hooks/useActiveTasks';

interface ActiveTasksListProps {
  tasks: ActiveTask[];
  onRemove: (taskId: string) => void;
  onNavigate?: (transcriptId: string) => void;
}

const STEP_LABELS: Record<string, string> = {
  'noise_suppression': 'Шумоподавление',
  'transcription': 'Транскрибация',
  'diarization': 'Диаризация',
  'summarization': 'Суммаризация',
  'db_save': 'Сохранение в БД',
  'rag_index': 'RAG индексация',
  'completed': 'Готово'
};

const STEP_ORDER = ['noise_suppression', 'transcription', 'diarization', 'summarization', 'db_save', 'rag_index', 'completed'];

const formatTime = (timestamp: number) => {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(timestamp));
};

const StatusDot = ({ status }: { status: ActiveTask['status'] }) => {
  const colorMap: Record<string, string> = {
    pending: '#787880',
    processing: '#3b82f6',
    completed: '#34d399',
    failed: '#f87171'
  };
  const isPulsing = status === 'processing';

  return (
    <span className="relative inline-flex items-center justify-center w-2 h-2">
      {isPulsing && (
        <span
          className="absolute inset-0 rounded-full progress-pulse"
          style={{ backgroundColor: colorMap[status], opacity: 0.35 }}
        />
      )}
      <span
        className="relative w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: colorMap[status] }}
      />
    </span>
  );
};

export const ActiveTasksList = ({ tasks, onRemove, onNavigate }: ActiveTasksListProps) => {
  if (tasks.length === 0) return null;

  const activeTasks = tasks.filter(t => t.status !== 'completed' && t.status !== 'failed');
  const completedTasks = tasks.filter(t => t.status === 'completed');

  const renderTask = (task: ActiveTask) => {
    const currentStepIndex = task.step ? STEP_ORDER.indexOf(task.step) : -1;
    const displayProgress = task.progress !== undefined && task.progress > 0
      ? task.progress
      : currentStepIndex >= 0
        ? ((currentStepIndex + 1) / STEP_ORDER.length) * 100
        : 25;

    const isCompleted = task.status === 'completed';
    const isFailed = task.status === 'failed';
    const isProcessing = task.status === 'processing';

    return (
      <div
        key={task.task_id}
        className="surface-base p-3 transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-center gap-2 mb-2">
              <StatusDot status={task.status} />
              <span className="text-sm font-medium text-gray-900 dark:text-[#f5f5f7] truncate">
                {task.task_id.slice(0, 12)}...
              </span>
              <span className="tabular text-[11px] text-gray-400 dark:text-[#6b6b75]">
                {formatTime(task.addedAt)}
              </span>
              <span
                className={`inline-flex items-center px-1.5 py-0.5 rounded-[5px] text-[9px] font-medium tracking-[0.02em]
                  ${isCompleted ? 'bg-emerald-500/10 text-emerald-400' : ''}
                  ${isFailed ? 'bg-red-500/10 text-red-400' : ''}
                  ${isProcessing ? 'bg-blue-500/10 text-blue-400' : ''}
                  ${task.status === 'pending' ? 'bg-[rgba(255,255,255,0.04)] text-[#a0a0a8]' : ''}
                `}
              >
                {task.status === 'pending' && 'В очереди'}
                {isProcessing && 'Обрабатывается'}
                {isCompleted && 'Готово'}
                {isFailed && 'Ошибка'}
              </span>
            </div>

            {/* Progress bar */}
            <div className="relative w-full h-[2px] rounded-full bg-[rgba(255,255,255,0.05)] mb-2 overflow-hidden">
              <div
                className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out
                  ${isCompleted ? 'bg-emerald-400/80' : isFailed ? 'bg-red-400/60' : 'bg-blue-500'}
                `}
                style={{ width: `${Math.min(displayProgress, 100)}%` }}
              >
                {isProcessing && <span className="absolute inset-0 shimmer" />}
              </div>
            </div>

            {/* Step + percent */}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-gray-500 dark:text-[#a0a0a8]">
                {task.step ? STEP_LABELS[task.step] || task.step : 'Обработка...'}
              </span>
              <span className="tabular text-[10px] text-gray-400 dark:text-[#6b6b75]">{Math.round(displayProgress)}%</span>
            </div>

            {/* Error */}
            {task.error && (
              <p className="text-[11px] text-red-400 mt-1">{task.error}</p>
            )}

            {/* Navigate CTA for completed */}
            {isCompleted && task.result?.transcript_id && (
              <button
                onClick={() => onNavigate?.(task.result!.transcript_id)}
                className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[7px] text-[11px] font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
                Открыть транскрипцию
              </button>
            )}
          </div>

          <button
            onClick={() => onRemove(task.task_id)}
            className="shrink-0 w-5 h-5 rounded-[5px] flex items-center justify-center text-[#6b6b75] hover:text-red-400 hover:bg-red-500/10 transition-colors"
            aria-label="Удалить"
          >
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="surface-base p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-[#f5f5f7]">
          Активные задачи
        </h3>
        <span className="tabular text-[11px] text-gray-400 dark:text-[#6b6b75]">
          {activeTasks.length} активн. · {completedTasks.length} готово
        </span>
      </div>

      <div className="space-y-2">
        {tasks.map(renderTask)}
      </div>
    </div>
  );
};
