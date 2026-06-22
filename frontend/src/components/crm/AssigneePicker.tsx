import { Popover } from './Popover';
import { getWeeekMemberColor } from '@/utils/weeekMemberColor';
import type { WeeekMember } from '@/api/crm';

interface AssigneePickerProps {
  members: WeeekMember[];
  /** Текущее значение — id выбранного члена (или null если "не назначать"). */
  value: string | null;
  onChange: (member: { id: string; name: string } | null) => void;
}

/** Резолвит id → имя для отображения; ищет в списке members. */
const resolveMember = (members: WeeekMember[], id: string | null) => {
  if (!id) return null;
  return members.find((m) => m.id === id) ?? { id, name: `User #${id}` };
};

export const AssigneePicker = ({ members, value, onChange }: AssigneePickerProps) => {
  const selected = resolveMember(members, value);
  const triggerColor = getWeeekMemberColor(selected?.id ?? '');

  return (
    <Popover
      trigger={(open, toggle) => {
        const hasValue = !!selected;
        const initial = selected?.name?.[0]?.toUpperCase() ?? '?';
        return (
          <button
            type="button"
            onClick={toggle}
            className={`group inline-flex items-center gap-1.5 h-7 pl-1.5 pr-2.5 rounded-md text-[11px] font-medium transition-colors ${
              hasValue
                ? `${triggerColor.bg} ${triggerColor.text} ring-1 ${triggerColor.ring}/30 hover:brightness-125`
                : open
                  ? 'bg-gray-100 text-gray-700 ring-1 ring-gray-300 dark:bg-white/5 dark:text-gray-300 dark:ring-white/15'
                  : 'bg-gray-50 text-gray-400 ring-1 ring-dashed ring-gray-300 hover:bg-gray-100 hover:text-gray-600 dark:bg-white/[0.03] dark:text-gray-400 dark:ring-white/10 dark:hover:bg-white/5 dark:hover:text-gray-300'
            }`}
            title="Назначить ответственного"
          >
            <span
              className={`w-3.5 h-3.5 rounded-full inline-flex items-center justify-center text-[9px] font-bold ring-1 ring-gray-300 dark:ring-white/15 ${
                hasValue
                  ? `${triggerColor.bg} ${triggerColor.text}`
                  : 'bg-gray-200 text-gray-500 dark:bg-white/5 dark:text-gray-400'
              }`}
            >
              {hasValue ? initial : '?'}
            </span>
            <span className="max-w-[10rem] truncate">
              {selected?.name ?? 'Назначить'}
            </span>
            <span className="opacity-60 text-[9px]">{open ? '▲' : '▼'}</span>
          </button>
        );
      }}
    >
      {(close) => {
        const items: Array<{ id: string; name: string }> = [
          { id: '', name: '— Не назначать —' },
          ...members.map((m) => ({ id: m.id, name: m.name })),
        ];
        const selectedId = selected?.id ?? '';
        return (
          <div className="max-h-64 overflow-y-auto">
            {items.map((user) => {
              const isSelected = selectedId === user.id;
              const c = getWeeekMemberColor(user.id || 'unassigned');
              const isUnassign = !user.id;
              return (
                <button
                  key={user.id || 'none'}
                  type="button"
                  onClick={() => {
                    onChange(user.id ? { id: user.id, name: user.name } : null);
                    close();
                  }}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 text-xs transition-colors ${
                    isSelected
                      ? `${c.bg} ${c.text}`
                      : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/5'
                  }`}
                >
                  <span
                    className={`w-5 h-5 rounded-full inline-flex items-center justify-center text-[9px] font-bold ring-1 ring-gray-300 dark:ring-white/15 ${
                      isUnassign
                        ? 'bg-gray-200 text-gray-500 dark:bg-white/5 dark:text-gray-500'
                        : `${c.bg} ${c.text}`
                    }`}
                  >
                    {isUnassign ? '∅' : user.name[0]?.toUpperCase() || '?'}
                  </span>
                  <span className="flex-1 text-left truncate">{user.name}</span>
                  {isSelected && <span className="text-[10px]">✓</span>}
                </button>
              );
            })}
          </div>
        );
      }}
    </Popover>
  );
};
