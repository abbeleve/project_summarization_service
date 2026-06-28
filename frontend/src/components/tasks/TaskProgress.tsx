import type { TaskInfo } from '@/types/transcript';

interface TaskProgressProps {
  task: TaskInfo;
  onCancel?: () => void;
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

const StatusDot = ({ status }: { status: TaskInfo['status'] }) => {
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

export const TaskProgress = ({ task, onCancel }: TaskProgressProps) => {
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
      className="surface-base p-4"
      style={{
        borderLeftWidth: 1,
        borderLeftColor: isCompleted
          ? 'rgba(52,211,153,0.35)'
          : isFailed
            ? 'rgba(248,113,113,0.35)'
            : 'rgba(59,130,246,0.35)'
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2.5 mb-3">
            <StatusDot status={task.status} />
            <span className="text-sm font-medium text-gray-900 dark:text-[#f5f5f7]">
              Задача {task.task_id.slice(0, 8)}...
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-medium tracking-[0.02em]
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
          <div className="relative w-full h-[3px] rounded-full bg-[rgba(255,255,255,0.05)] mb-3 overflow-hidden">
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
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-gray-500 dark:text-[#a0a0a8]">
              Этап: <span className="text-gray-900 dark:text-[#f5f5f7] font-medium">{STEP_LABELS[task.step || ''] || 'Обработка...'}</span>
            </span>
            <span className="tabular text-[11px] text-gray-400 dark:text-[#6b6b75]">{Math.round(displayProgress)}%</span>
          </div>

          {/* Step-dot segments */}
          <div className="flex gap-1">
            {STEP_ORDER.filter(s => s !== 'completed').map((step, index) => (
              <div
                key={step}
                className={`flex-1 h-[2px] rounded-full transition-colors duration-300 ${
                  index <= currentStepIndex ? 'bg-blue-500/60' : 'bg-[rgba(255,255,255,0.04)]'
                }`}
              />
            ))}
          </div>

          {/* Error */}
          {task.error && (
            <div className="mt-3 px-3 py-2 rounded-[8px] bg-red-500/8 border border-red-500/12">
              <p className="text-xs text-red-400">{task.error}</p>
            </div>
          )}

          {/* Success */}
          {isCompleted && (
            <div className="mt-3 px-3 py-2 rounded-[8px] bg-emerald-500/8 border border-emerald-500/12">
              <p className="text-xs text-emerald-400">Транскрипция готова! Страница будет перезагружена...</p>
            </div>
          )}
        </div>

        {onCancel && !isCompleted && !isFailed && (
          <button
            onClick={onCancel}
            className="shrink-0 w-6 h-6 rounded-[6px] flex items-center justify-center text-[#6b6b75] hover:text-red-400 hover:bg-red-500/10 transition-colors"
            aria-label="Отменить"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};
