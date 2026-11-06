import React from 'react';

interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading data...',
  size = 'md',
  className = ''
}) => {
  const spinnerSize = size === 'sm' ? 'h-4 w-4' : size === 'lg' ? 'h-8 w-8' : 'h-5 w-5';

  return (
    <div className={`p-8 flex flex-col items-center justify-center text-slate-400 gap-2.5 ${className}`}>
      <div className={`${spinnerSize} border-2 border-brand-500 border-t-transparent rounded-full animate-spin`} />
      {message && <span className="text-xs text-slate-400">{message}</span>}
    </div>
  );
};
