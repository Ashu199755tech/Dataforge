import React, { useState, useRef, useEffect } from 'react';
import { Search, X, ArrowUpDown, ArrowUp, ArrowDown, Check, ChevronDown, SlidersHorizontal } from 'lucide-react';

export interface SortOption {
  id: string;
  label: string;
}

interface ListFilterSortBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchPlaceholder?: string;
  sortOptions?: SortOption[];
  currentSort?: string;
  onSortChange?: (sortId: string) => void;
  sortDirection?: 'asc' | 'desc';
  onToggleDirection?: () => void;
  totalCount?: number;
  filteredCount?: number;
  className?: string;
  children?: React.ReactNode;
}

export const ListFilterSortBar: React.FC<ListFilterSortBarProps> = ({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search items...',
  sortOptions = [
    { id: 'newest', label: 'Newest First' },
    { id: 'oldest', label: 'Oldest First' },
    { id: 'name_asc', label: 'Name (A to Z)' },
    { id: 'name_desc', label: 'Name (Z to A)' },
  ],
  currentSort = 'newest',
  onSortChange,
  sortDirection = 'desc',
  onToggleDirection,
  totalCount,
  filteredCount,
  className = '',
  children
}) => {
  const [isSortOpen, setIsSortOpen] = useState(false);
  const sortRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sortRef.current && !sortRef.current.contains(event.target as Node)) {
        setIsSortOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeSortOption = sortOptions.find((opt) => opt.id === currentSort) || sortOptions[0];

  return (
    <div className={`flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800/80 backdrop-blur-sm ${className}`}>
      {/* Left side: Custom children filters/tabs if provided */}
      <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
        {children}
        {typeof totalCount === 'number' && (
          <span className="text-[11px] text-slate-500 font-medium px-2 py-1 rounded bg-slate-800/50 hidden sm:inline-block">
            {typeof filteredCount === 'number' && filteredCount !== totalCount
              ? `Showing ${filteredCount} of ${totalCount}`
              : `${totalCount} item${totalCount === 1 ? '' : 's'}`}
          </span>
        )}
      </div>

      {/* Right side: Search Input & Sort By Controls */}
      <div className="flex items-center gap-2 self-stretch md:self-auto shrink-0">
        {/* Search Bar */}
        <div className="relative flex-1 md:w-64">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800/90 rounded-lg pl-9 pr-8 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 transition shadow-inner"
          />
          {searchQuery && (
            <button
              onClick={() => {
                onSearchChange('');
                inputRef.current?.focus();
              }}
              className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300 p-0.5 rounded transition"
              title="Clear search"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Sort By Dropdown Button */}
        {onSortChange && sortOptions.length > 0 && (
          <div className="relative" ref={sortRef}>
            <div className="flex items-center rounded-lg border border-slate-800/90 bg-slate-950/80 shadow-sm overflow-hidden">
              <button
                type="button"
                onClick={() => setIsSortOpen((prev) => !prev)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800/60 transition"
                title="Sort items"
              >
                <SlidersHorizontal className="h-3 w-3 text-brand-400" />
                <span className="hidden sm:inline text-slate-400">Sort:</span>
                <span className="max-w-[110px] truncate font-semibold text-slate-200">
                  {activeSortOption?.label || 'Sort'}
                </span>
                <ChevronDown className="h-3 w-3 text-slate-500 ml-0.5" />
              </button>

              {onToggleDirection && (
                <button
                  type="button"
                  onClick={onToggleDirection}
                  className="px-2 py-1.5 text-slate-400 hover:text-white hover:bg-slate-800/80 border-l border-slate-800/90 transition"
                  title={`Direction: ${sortDirection === 'asc' ? 'Ascending' : 'Descending'}`}
                >
                  {sortDirection === 'asc' ? (
                    <ArrowUp className="h-3 w-3 text-brand-400" />
                  ) : (
                    <ArrowDown className="h-3 w-3 text-brand-400" />
                  )}
                </button>
              )}
            </div>

            {/* Sort Options Menu */}
            {isSortOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-48 bg-slate-900 border border-slate-700/80 rounded-lg shadow-xl z-50 p-1 divide-y divide-slate-800/60">
                <div className="px-2.5 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Sort By</span>
                  <span className="text-[9px] text-brand-400 font-mono">
                    {sortDirection === 'asc' ? 'ASC' : 'DESC'}
                  </span>
                </div>
                <div className="py-1 space-y-0.5">
                  {sortOptions.map((option) => {
                    const isSelected = option.id === currentSort;
                    return (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => {
                          onSortChange(option.id);
                          setIsSortOpen(false);
                        }}
                        className={`w-full text-left px-2.5 py-1.5 rounded-md text-xs flex items-center justify-between transition ${
                          isSelected
                            ? 'bg-brand-600/20 text-brand-300 font-semibold'
                            : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                        }`}
                      >
                        <span className="truncate">{option.label}</span>
                        {isSelected && <Check className="h-3.5 w-3.5 text-brand-400 shrink-0 ml-1" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
