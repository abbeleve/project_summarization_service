interface CrmDropdownItem {
  key: string;
  label: string;
  selected: boolean;
  onSelect: () => void;
}

interface CrmDropdownProps {
  items: CrmDropdownItem[];
  onClear?: () => void;
  empty?: string;
}

/** Общий выпадающий список для каскада Проект → Доска → Колонка.
 *  Стилизован под наш dark/glass + light theme. */
export const CrmDropdown = ({ items, onClear, empty }: CrmDropdownProps) => (
  <div className="absolute z-30 mt-1 left-0 w-64 rounded-xl bg-white border border-gray-200 shadow-lg shadow-gray-200/50 dark:bg-[#0e1622]/95 dark:border-white/10 dark:shadow-2xl dark:shadow-black/40 py-1.5 max-h-64 overflow-y-auto">
    {onClear && (
      <button
        type="button"
        onClick={onClear}
        className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:text-gray-500 dark:hover:bg-white/5"
      >
        ∅ Не выбрано
      </button>
    )}
    {items.length === 0 ? (
      <p className="px-3 py-2 text-xs text-gray-400 dark:text-gray-500">{empty ?? 'Нет элементов'}</p>
    ) : (
      items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={item.onSelect}
          className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs transition-colors ${
            item.selected
              ? 'bg-indigo-100 text-indigo-700 ring-1 ring-inset ring-indigo-200 dark:bg-indigo-500/15 dark:text-indigo-100 dark:ring-indigo-400/30'
              : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/5'
          }`}
        >
          <span className="flex-1 text-left truncate">{item.label}</span>
          {item.selected && <span className="text-[10px]">✓</span>}
        </button>
      ))
    )}
  </div>
);
