import React from 'react';

export interface ColumnDef<T> {
  key: string;
  header: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (row: T, index: number) => React.ReactNode;
}

interface StudioTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  keyField?: keyof T | ((row: T) => string);
  onRowClick?: (row: T) => void;
  className?: string;
}

export function StudioTable<T>({
  columns,
  data,
  loading = false,
  emptyTitle = 'No records found',
  emptyDescription,
  keyField = 'id' as any,
  onRowClick,
  className = ''
}: StudioTableProps<T>) {
  const getRowKey = (row: T, index: number): string => {
    if (typeof keyField === 'function') {
      return keyField(row);
    }
    return (row[keyField] as any) || String(index);
  };

  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] font-semibold tracking-wider border-b border-slate-800">
          <tr>
            {columns.map((col, i) => (
              <th
                key={col.key}
                style={{ width: col.width }}
                className={`py-2 px-3 ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'} ${
                  i === 0 ? 'rounded-l' : i === columns.length - 1 ? 'rounded-r' : ''
                }`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60">
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="py-8 text-center text-slate-500">
                <div className="flex items-center justify-center gap-2">
                  <div className="h-4 w-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                  <span>Loading records...</span>
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="py-8 text-center text-slate-500">
                <div className="font-medium text-slate-400">{emptyTitle}</div>
                {emptyDescription && (
                  <div className="text-[11px] text-slate-600 mt-0.5">{emptyDescription}</div>
                )}
              </td>
            </tr>
          ) : (
            data.map((row, index) => (
              <tr
                key={getRowKey(row, index)}
                onClick={() => onRowClick && onRowClick(row)}
                className={`transition-colors ${
                  onRowClick ? 'cursor-pointer hover:bg-slate-800/50' : 'hover:bg-slate-800/30'
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`py-2.5 px-3 text-slate-300 ${
                      col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                    }`}
                  >
                    {col.render ? col.render(row, index) : (row as any)[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
