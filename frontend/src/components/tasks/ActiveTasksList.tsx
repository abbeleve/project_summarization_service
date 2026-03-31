import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { ActiveTask } from '@/hooks/useActiveTasks';

interface ActiveTasksListProps {
  tasks: ActiveTask[];
  onRemove: (taskId: string) => void;
  onNavigate?: (transcriptId: string) => void;
}

const STEP_LABELS: Record<string, string> = {
  'noise_suppression': '🔇 Шумоподавление',
  'transcription': '📝 Транскрибация',
  'diarization': '🗣️ Диаризация',
  'summarization': '📋 Суммаризация',
  'rag_index': '📚 RAG индексация',
  'completed': '✅ Готово'
};

const STEP_ORDER = ['noise_suppression', 'transcription', 'diarization', 'summarization', 'rag_index', 'completed'];

const formatTime = (timestamp: number) => {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(timestamp));
};

export const ActiveTasksList = ({ tasks, onRemove, onNavigate }: ActiveTasksListProps) => {
  if (tasks.length === 0) return null;

  const activeTasks = tasks.filter(t => t.status !== 'completed' && t.status !== 'failed');
  const completedTasks = tasks.filter(t => t.status === 'completed');
  const failedTasks = tasks.filter(t => t.status === 'failed');

  const renderTask = (task: ActiveTask) => {
    const currentStepIndex = task.step ? STEP_ORDER.indexOf(task.step) : -1;
    const displayProgress = task.progress !== undefined && task.progress > 0
      ? task.progress
      : currentStepIndex >= 0
        ? ((currentStepIndex + 1) / STEP_ORDER.length) * 100
        : 25;

    const getStatusColor = () => {
      switch (task.status) {
        case 'pending': return 'bg-yellow-500';
        case 'processing': return 'bg-blue-500';
        case 'completed': return 'bg-green-500';
        case 'failed': return 'bg-red-500';
        default: return 'bg-gray-500';
      }
    };

    const getStatusText = () => {
      switch (task.status) {
        case 'pending': return 'В очереди';
        case 'processing': return 'Обрабатывается';
        case 'completed': return 'Готово';
        case 'failed': return 'Ошибка';
        default: return '';
      }
    };

    return (
      <div
        key={task.task_id}
        className="p-3 border rounded-lg hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-2.5 h-2.5 rounded-full ${
                task.status === 'processing' ? 'animate-pulse' : ''
              } ${getStatusColor()}`} />
              <span className="font-medium text-gray-900 text-sm truncate">
                {task.task_id.slice(0, 12)}...
              </span>
              <span className="text-xs text-gray-500">
                {formatTime(task.addedAt)}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                task.status === 'completed' ? 'bg-green-100 text-green-700' :
                task.status === 'failed' ? 'bg-red-100 text-red-700' :
                'bg-blue-100 text-blue-700'
              }`}>
                {getStatusText()}
              </span>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-gray-200 rounded-full h-1.5 mb-2">
              <div
                className={`h-1.5 rounded-full transition-all duration-500 ${getStatusColor()}`}
                style={{ width: `${Math.min(displayProgress, 100)}%` }}
              />
            </div>

            {/* Step info */}
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-600">
                {task.step ? STEP_LABELS[task.step] || task.step : 'Обработка...'}
              </span>
              <span className="text-gray-500">{Math.round(displayProgress)}%</span>
            </div>

            {/* Error message */}
            {task.error && (
              <p className="text-xs text-red-600 mt-1">
                ❌ {task.error}
              </p>
            )}

            {/* Completed - show navigate button */}
            {task.status === 'completed' && task.result?.transcript_id && (
              <Button
                variant="primary"
                size="sm"
                className="mt-2"
                onClick={() => onNavigate?.(task.result.transcript_id)}
              >
                📊 Открыть транскрипцию
              </Button>
            )}
          </div>

          <button
            onClick={() => onRemove(task.task_id)}
            className="text-gray-400 hover:text-red-600 transition-colors flex-shrink-0"
            title="Закрыть"
          >
            ✕
          </button>
        </div>
      </div>
    );
  };

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-gray-900">
          📋 Активные задачи ({tasks.length})
        </h3>
        <span className="text-xs text-gray-500">
          Активных: {activeTasks.length} | Готово: {completedTasks.length}
        </span>
      </div>

      <div className="space-y-2">
        {tasks.map(renderTask)}
      </div>
    </Card>
  );
};
