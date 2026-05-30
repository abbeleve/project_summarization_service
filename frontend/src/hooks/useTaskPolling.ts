import { useEffect, useRef, useCallback, useState } from 'react';
import apiClient from '@/api/client';
import type { TaskInfo, TaskStatus } from '@/types/transcript';

interface UseTaskPollingOptions {
  taskId: string | null;
  onProgress?: (task: TaskInfo) => void;
  onComplete?: (task: TaskInfo) => void;
  onError?: (error: string) => void;
  pollInterval?: number;
  enabled?: boolean;
}

interface UseTaskPollingReturn {
  task: TaskInfo | null;
  isLoading: boolean;
  error: string | null;
  cancelPolling: () => void;
}

export const useTaskPolling = ({
  taskId,
  onProgress,
  onComplete,
  onError,
  pollInterval = 5000, // 5 секунд по умолчанию
  enabled = true
}: UseTaskPollingOptions): UseTaskPollingReturn => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const taskIdRef = useRef<string | null>(taskId);
  const [task, setTask] = useState<TaskInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchTaskStatus = useCallback(async (id: string) => {
    try {
      const response = await apiClient.get<TaskInfo>(`/tasks/${id}`);
      const taskData = response.data;

      setTask(taskData);

      if (onProgress) {
        onProgress(taskData);
      }

      if (taskData.status === 'completed') {
        if (onComplete) {
          onComplete(taskData);
        }
        return true; // Задача завершена
      }

      if (taskData.status === 'failed') {
        const errorMsg = taskData.error || 'Неизвестная ошибка';
        setError(errorMsg);
        if (onError) {
          onError(errorMsg);
        }
        return true; // Задача провалена
      }

      return false; // Продолжать опрос
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Ошибка получения статуса';
      setError(errorMessage);
      if (onError) {
        onError(errorMessage);
      }
      return true; // Ошибка, прекращаем опрос
    }
  }, [onProgress, onComplete, onError]);

  useEffect(() => {
    taskIdRef.current = taskId;
  }, [taskId]);

  useEffect(() => {
    if (!enabled || !taskId) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    let cancelled = false;

    const poll = async () => {
      if (!taskIdRef.current) return;

      const shouldStop = await fetchTaskStatus(taskIdRef.current);
      if (shouldStop || cancelled) {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    };

    // Первый запрос сразу
    poll();

    // Затем опрос каждые pollInterval
    intervalRef.current = setInterval(poll, pollInterval);

    return () => {
      cancelled = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [taskId, enabled, fetchTaskStatus, pollInterval]);

  const cancelPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  return {
    task,
    isLoading: !!taskId && task?.status !== 'completed' && task?.status !== 'failed',
    error,
    cancelPolling
  };
};
