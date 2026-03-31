interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onPageChange: (newOffset: number) => void;
}

export const Pagination = ({ total, limit, offset, onPageChange }: PaginationProps) => {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  if (totalPages <= 1) return null;

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    <div className="flex items-center justify-center gap-2 mt-6">
      <button
        onClick={() => onPageChange(0)}
        disabled={currentPage === 1}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        ← Первая
      </button>

      <button
        onClick={() => onPageChange(offset - limit)}
        disabled={currentPage === 1}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        ← Назад
      </button>

      <div className="flex items-center gap-1">
        {pages.map(page => {
          const pageOffset = (page - 1) * limit;
          const isActive = page === currentPage;

          return (
            <button
              key={page}
              onClick={() => onPageChange(pageOffset)}
              className={`px-3 py-1 text-sm border rounded ${
                isActive
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'hover:bg-gray-50'
              }`}
            >
              {page}
            </button>
          );
        })}
      </div>

      <button
        onClick={() => onPageChange(offset + limit)}
        disabled={currentPage === totalPages}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Вперёд →
      </button>

      <button
        onClick={() => onPageChange((totalPages - 1) * limit)}
        disabled={currentPage === totalPages}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Последняя →
      </button>
    </div>
  );
};
