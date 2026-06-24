import { useState } from 'react';
import type { MeetingTask } from '@/types/transcript';
import type { WeeekMember } from '@/api/crm';
import { AssigneePicker } from './AssigneePicker';
import { DeadlinePicker } from './DeadlinePicker';

export interface TaskCardCallbacks {
  localAssignees: Record<string, string>;
  setLocalAssignees: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  taskWeeekUserIds: Record<string, string>;
  setTaskWeeekUserIds: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  localDeadlines: Record<string, string>;
  setLocalDeadlines: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  isSendingOne: boolean;
  isDeleting: boolean;
  onSend: (taskId: string) => void;
  onDelete: (taskId: string) => void;
  onSaveDescription: (taskId: string, description: string) => void;
  /** Если true — CRM не подключена: блокируем assignee/deadline/send. */
  crmDisabled?: boolean;
}

interface TaskCardProps {
  task: MeetingTask;
  index: number;
  members: WeeekMember[];
  cb: TaskCardCallbacks;
  /** false — не показывать номер (для отправленных задач) */
  showNumber?: boolean;
}

const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });

export const TaskCard = ({ task, index, members, cb, showNumber = true }: TaskCardProps) => {
  const isSent = task.sent_to_crm;
  const [showTrashConfirm, setShowTrashConfirm] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState(task.description);

  const effectiveDeadline = cb.localDeadlines[task.id] ?? task.deadline ?? undefined;

  // Явный сброс (юзер нажал «Не назначать») — ставим null для picker
  const assigneeCleared = cb.localAssignees[task.id] === '';
  const pickerValueId = assigneeCleared ? null : (cb.taskWeeekUserIds[task.id] ?? null);

  // Подсказка от нейросети: показываем под пикером если ещё не выбрали вручную
  const aiSuggestion = (cb.localAssignees[task.id] === undefined && task.assignee) ? task.assignee : null;

  return (
    <div
      className={`group relative rounded-2xl border transition-all duration-200 ${
        isSent
          ? 'border-gray-200 bg-gray-50 dark:border-white/[0.04] dark:bg-white/[0.015]'
          : 'border-gray-200 bg-white hover:border-emerald-300 hover:shadow-[0_4px_16px_-6px_rgba(5,150,105,0.2)] dark:border-white/[0.06] dark:bg-white/[0.025] dark:hover:border-white/10 dark:hover:bg-white/[0.04] dark:hover:shadow-[0_8px_30px_-12px_rgba(16,185,129,0.2)]'
      }`}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        {/* Круглый бейдж с номером */}
        <span
          className={`flex-shrink-0 w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center mt-0.5 ${
            isSent
              ? 'bg-gray-200 text-gray-500 dark:bg-white/[0.06] dark:text-gray-500'
              : showNumber
                ? 'bg-emerald-500 text-white dark:bg-emerald-500 dark:text-white'
                : 'bg-gray-100 text-transparent dark:bg-white/[0.03]'
          }`}
        >
          {showNumber ? index + 1 : '✓'}
        </span>

        <div className="flex-1 min-w-0">
          {/* Описание */}
          {isSent ? (
            <p className="text-sm leading-relaxed text-gray-400 line-through">
              {task.description}
            </p>
          ) : editingDesc ? (
            <div className="space-y-1">
              <textarea
                autoFocus
                value={descDraft}
                onChange={(e) => setDescDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    setDescDraft(task.description);
                    setEditingDesc(false);
                  }
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const trimmed = descDraft.trim();
                    if (trimmed && trimmed !== task.description) {
                      cb.onSaveDescription(task.id, trimmed);
                    }
                    setEditingDesc(false);
                  }
                }}
                onBlur={() => {
                  const trimmed = descDraft.trim();
                  if (trimmed && trimmed !== task.description) {
                    cb.onSaveDescription(task.id, trimmed);
                  }
                  setEditingDesc(false);
                }}
                className="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 border border-gray-300 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none dark:bg-white/[0.04] dark:border-white/10 dark:text-gray-100 dark:placeholder-gray-500 dark:focus:ring-emerald-400/40"
                rows={3}
              />
              <p className="text-[10px] text-gray-400 dark:text-gray-500">
                ↵ Enter — сохранить · Esc — отмена · Shift+↵ — новая строка
              </p>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => {
                setDescDraft(task.description);
                setEditingDesc(true);
              }}
              className="block w-full text-left text-sm leading-relaxed text-gray-800 hover:text-gray-900 hover:bg-gray-50 transition-colors cursor-text px-1 -mx-1 rounded dark:text-gray-200 dark:hover:text-white dark:hover:bg-white/[0.04]"
              title="Редактировать задачу"
            >
              {task.description}
            </button>
          )}

          {/* Нижняя панель — появляется при наведении */}
          <div
            className="overflow-hidden group-hover:overflow-visible transition-all duration-200 max-h-0 group-hover:max-h-48 opacity-0 group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex flex-wrap items-center gap-2 mt-2.5">
            {isSent ? (
              <>
                <span className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-medium bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-400/20">
                  ✓ Отправлено в Weeek
                </span>
                {task.sent_at && (
                  <span className="text-[11px] text-gray-400 tabular-nums dark:text-gray-500">
                    {formatDateTime(task.sent_at)}
                  </span>
                )}
                {task.assignee && (
                  <span className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] text-gray-500 bg-gray-100 ring-1 ring-gray-200 dark:text-gray-400 dark:bg-white/[0.03] dark:ring-white/[0.06]">
                    👤 {task.assignee}
                  </span>
                )}
                {task.deadline && (
                  <span className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] text-gray-500 bg-gray-100 ring-1 ring-gray-200 dark:text-gray-400 dark:bg-white/[0.03] dark:ring-white/[0.06]">
                    ⏰ {formatDate(task.deadline)}
                  </span>
                )}
              </>
            ) : (
              <>
                <AssigneePicker
                  members={members}
                  value={pickerValueId}
                  disabled={cb.crmDisabled}
                  onChange={(choice) => {
                    if (!choice) {
                      cb.setLocalAssignees((prev) => ({ ...prev, [task.id]: '' }));
                      cb.setTaskWeeekUserIds((prev) => { const c = { ...prev }; delete c[task.id]; return c; });
                      return;
                    }
                    cb.setLocalAssignees((prev) => ({ ...prev, [task.id]: choice.name }));
                    cb.setTaskWeeekUserIds((prev) => ({ ...prev, [task.id]: choice.id }));
                  }}
                />
                <DeadlinePicker
                  value={effectiveDeadline}
                  disabled={cb.crmDisabled}
                  onChange={(iso) => {
                    if (iso === null) {
                      cb.setLocalDeadlines((prev) => { const c = { ...prev }; delete c[task.id]; return c; });
                      return;
                    }
                    cb.setLocalDeadlines((prev) => ({ ...prev, [task.id]: iso }));
                  }}
                />
                <button
                  type="button"
                  onClick={cb.crmDisabled ? undefined : cb.onSend.bind(null, task.id)}
                  aria-disabled={cb.crmDisabled || cb.isSendingOne}
                  disabled={cb.crmDisabled || cb.isSendingOne}
                  className={`inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-[11px] font-medium transition-all shadow-sm ${
                    cb.crmDisabled
                      ? 'bg-gray-200 text-gray-400 ring-1 ring-gray-300 dark:bg-white/[0.04] dark:text-gray-500 dark:ring-white/10 cursor-not-allowed'
                      : 'bg-emerald-600 text-white ring-1 ring-emerald-400/40 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-wait dark:bg-emerald-500/85 dark:ring-emerald-400/30 dark:hover:bg-emerald-500 dark:shadow-emerald-900/30'
                  }`}
                  title={cb.crmDisabled ? 'Сначала подключите Weeek API в Настройках' : 'Отправить эту задачу'}
                >
                  {cb.isSendingOne ? '⏳' : '📤'}
                  <span>{cb.isSendingOne ? 'Отправка…' : 'Отправить'}</span>
                </button>
              </>
            )}

            <div className="flex-1" />

            <button
              type="button"
              onClick={() => {
                if (showTrashConfirm || window.confirm('Удалить задачу?')) {
                  setShowTrashConfirm(false);
                  cb.onDelete(task.id);
                } else {
                  setShowTrashConfirm(true);
                  setTimeout(() => setShowTrashConfirm(false), 2500);
                }
              }}
              disabled={cb.isDeleting}
              className="inline-flex items-center justify-center w-7 h-7 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50 dark:text-gray-500 dark:hover:text-red-300 dark:hover:bg-red-500/10"
              title={showTrashConfirm ? 'Точно удалить?' : 'Удалить задачу'}
            >
              {showTrashConfirm ? '❓' : '🗑️'}
            </button>
            </div>
          </div>

          {!isSent && aiSuggestion && (
            <div className="overflow-hidden group-hover:overflow-visible transition-all duration-200 max-h-0 group-hover:max-h-12">
              <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-amber-50/70 text-amber-700 ring-1 ring-amber-200/50 dark:bg-amber-400/8 dark:text-amber-300 dark:ring-amber-400/20">
                ✨ Нейросеть предлагает: <strong>{aiSuggestion}</strong>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
