import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { TaskInfo } from '@/types/transcript';

interface TaskProgressProps {
  task: TaskInfo;
  onCancel?: () => void;
}

const STEP_LABELS: Record<string, string> = {
  'noise_suppression': '🔇 Шумоподавление',
  'transcription': '📝 Транскрибация',
  'diarization': '🗣️ Диаризация',
  'summarization': '📋 Суммаризация',
  'completed': '✅ Готово'
};

const STEP_ORDER = ['noise_suppression', 'transcription', 'diarization', 'summarization', 'completed'];

export const TaskProgress = ({ task, onCancel }: TaskProgressProps) => {
  const stepLabel = task.step ? (STEP_LABELS[task.step] || task.step) : 'Обработка...';
  const currentStepIndex = task.step ? STEP_ORDER.indexOf(task.step) : -1;

  const getStatusColor = () => {
    switch (task.status) {
      case 'pending':
        return 'bg-yellow-500';
      case 'processing':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = () => {
    switch (task.status) {
      case 'pending':
        return 'В очереди...';
      case 'processing':
        return 'Обрабатывается';
      case 'completed':
        return 'Готово';
      case 'failed':
        return 'Ошибка';
      default:
        return '';
    }
  };

  // Calculate progress based on current step if not provided
  const displayProgress = task.progress !== undefined && task.progress > 0
    ? task.progress
    : currentStepIndex >= 0
      ? ((currentStepIndex + 1) / STEP_ORDER.length) * 100
      : 25;

  return (
    <Card className={`p-4 bg-white border-l-4 ${
      task.status === 'completed' ? 'border-l-green-500' :
      task.status === 'failed' ? 'border-l-red-500' :
      'border-l-blue-500'
    }`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <div className={`w-3 h-3 rounded-full ${
              task.status === 'processing' ? 'animate-pulse' : ''
            } ${getStatusColor()}`} />
            <span className="font-medium text-gray-900">Задача {task.task_id.slice(0, 8)}...</span>
            <span className="text-sm text-gray-500">{getStatusText()}</span>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
            <div
              className={`h-3 rounded-full transition-all duration-500 ${getStatusColor()}`}
              style={{ width: `${Math.min(displayProgress, 100)}%` }}
            />
          </div>

          {/* Current step */}
          <div className="flex items-center justify-between text-sm">
            <p className="text-gray-600">
              Этап: <span className="font-medium text-gray-900">{stepLabel}</span>
            </p>
            <p className="text-gray-500">
              {Math.round(displayProgress)}%
            </p>
          </div>

          {/* Step indicators */}
          <div className="flex gap-1 mt-3">
            {STEP_ORDER.filter(s => s !== 'completed').map((step, index) => (
              <div
                key={step}
                className={`flex-1 h-1.5 rounded-full ${
                  index <= currentStepIndex ? getStatusColor() : 'bg-gray-200'
                }`}
              />
            ))}
          </div>

          {/* Error message */}
          {task.error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">
                ❌ {task.error}
              </p>
            </div>
          )}

          {/* Success message */}
          {task.status === 'completed' && (
            <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-800">
                ✅ Транскрипция готова! Страница будет перезагружена...
              </p>
            </div>
          )}
        </div>

        {onCancel && task.status !== 'completed' && task.status !== 'failed' && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            className="text-red-600 hover:text-red-700"
          >
            ✕
          </Button>
        )}
      </div>
    </Card>
  );
};
