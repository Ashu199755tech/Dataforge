import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Inbox,
  title,
  description,
  actionText,
  onAction,
  className = ''
}) => {
  return (
    <div className={`p-8 rounded-xl border border-dashed border-slate-800 text-center flex flex-col items-center justify-center ${className}`}>
      <div className="h-10 w-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mb-3 shadow-inner">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="text-xs font-semibold text-slate-300">{title}</h3>
      {description && (
        <p className="text-[11px] text-slate-500 max-w-sm mt-1">{description}</p>
      )}
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-3 py-1.5 rounded-lg text-xs font-medium bg-brand-600 hover:bg-brand-500 text-white transition shadow-sm"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
