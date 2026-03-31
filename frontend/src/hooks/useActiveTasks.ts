import { useEffect, useCallback, useState } from 'react';
import apiClient from '@/api/client';
import type { TaskInfo } from '@/types/transcript';

export interface ActiveTask extends TaskInfo {
  addedAt: number;
}

interface UseActiveTasksReturn {
  tasks: ActiveTask[];
  addTask: (taskId: string) => void;
  removeTask: (taskId: string) => void;
  clearCompleted: () => void;
}

const STORAGE_KEY = 'activeTasks';

// Загружаем задачи из localStorage при инициализации
const loadTasksFromStorage = (): ActiveTask[] => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to load tasks from storage:', e);
  }
  return [];
};

// Сохраняем задачи в localStorage
const saveTasksToStorage = (tasks: ActiveTask[]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  } catch (e) {
    console.error('Failed to save tasks to storage:', e);
  }
};

export const useActiveTasks = (): UseActiveTasksReturn => {
  const [tasks, setTasks] = useState<ActiveTask[]>(loadTasksFromStorage);

  // Обновляем статус задач каждые 5 секунд
  useEffect(() => {
    if (tasks.length === 0) return;

    const updateTasks = async () => {
      const updatedTasks = await Promise.all(
        tasks.map(async (task) => {
          // Не обновляем завершённые задачи
          if (task.status === 'completed' || task.status === 'failed') {
            return task;
          }

          try {
            const response = await apiClient.get<TaskInfo>(`/tasks/${task.task_id}`);
            return { ...response.data, addedAt: task.addedAt };
          } catch (e) {
            console.error(`Failed to update task ${task.task_id}:`, e);
            return task;
          }
        })
      );

      setTasks(updatedTasks);
      saveTasksToStorage(updatedTasks);
    };

    updateTasks();
    const interval = setInterval(updateTasks, 5000);
    return () => clearInterval(interval);
  }, [tasks.map(t => t.task_id).join(',')]); // Обновляем при изменении списка ID

  const addTask = useCallback((taskId: string) => {
    setTasks(prev => {
      // Проверяем, нет ли уже такой задачи
      if (prev.some(t => t.task_id === taskId)) {
        return prev;
      }
      const newTask: ActiveTask = {
        task_id: taskId,
        status: 'pending',
        step: 'transcription',
        progress: 0,
        addedAt: Date.now()
      };
      const updated = [...prev, newTask];
      saveTasksToStorage(updated);
      return updated;
    });
  }, []);

  const removeTask = useCallback((taskId: string) => {
    setTasks(prev => {
      const updated = prev.filter(t => t.task_id !== taskId);
      saveTasksToStorage(updated);
      return updated;
    });
  }, []);

  const clearCompleted = useCallback(() => {
    setTasks(prev => {
      const updated = prev.filter(t => t.status !== 'completed' && t.status !== 'failed');
      saveTasksToStorage(updated);
      return updated;
    });
  }, []);

  return {
    tasks,
    addTask,
    removeTask,
    clearCompleted
  };
};
