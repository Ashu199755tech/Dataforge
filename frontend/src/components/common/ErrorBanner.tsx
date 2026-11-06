import React from 'react';
import { AlertTriangle, XCircle, RotateCcw } from 'lucide-react';

interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  severity?: 'error' | 'warning';
  className?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title,
  message,
  onRetry,
  severity = 'error',
  className = ''
}) => {
  const isError = severity === 'error';
  const Icon = isError ? XCircle : AlertTriangle;

  return (
    <div className={`p-3.5 rounded-xl border flex items-start justify-between gap-3 ${
      isError 
        ? 'bg-rose-500/10 border-rose-500/25 text-rose-300' 
        : 'bg-amber-500/10 border-amber-500/25 text-amber-300'
    } ${className}`}>
      <div className="flex items-start gap-2.5">
        <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${isError ? 'text-rose-400' : 'text-amber-400'}`} />
        <div className="text-xs">
          {title && <div className="font-semibold text-white mb-0.5">{title}</div>}
          <div className="text-[11px] opacity-90">{message}</div>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 text-slate-200 transition shrink-0"
        >
          <RotateCcw className="h-3 w-3" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
