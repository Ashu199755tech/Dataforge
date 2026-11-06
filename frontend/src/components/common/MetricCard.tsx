import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

export type ColorVariant = 'blue' | 'purple' | 'emerald' | 'amber' | 'rose' | 'teal' | 'cyan' | 'slate';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon?: LucideIcon;
  colorVariant?: ColorVariant;
  trend?: {
    value: string | number;
    isPositive?: boolean;
    label?: string;
  };
  badge?: string;
  onClick?: () => void;
  loading?: boolean;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtext,
  icon: Icon,
  colorVariant = 'blue',
  trend,
  badge,
  onClick,
  loading = false,
  className = ''
}) => {
  const variantStyles = {
    blue: {
      border: 'border-slate-800 hover:border-brand-500/40',
      iconBg: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      valueColor: 'text-white',
      accentColor: 'text-brand-400'
    },
    purple: {
      border: 'border-slate-800 hover:border-purple-500/40',
      iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      valueColor: 'text-white',
      accentColor: 'text-purple-400'
    },
    emerald: {
      border: 'border-slate-800 hover:border-emerald-500/40',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      valueColor: 'text-emerald-400',
      accentColor: 'text-emerald-400'
    },
    amber: {
      border: 'border-slate-800 hover:border-amber-500/40',
      iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      valueColor: 'text-amber-400',
      accentColor: 'text-amber-400'
    },
    rose: {
      border: 'border-slate-800 hover:border-rose-500/40',
      iconBg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      valueColor: 'text-rose-400',
      accentColor: 'text-rose-400'
    },
    teal: {
      border: 'border-slate-800 hover:border-teal-500/40',
      iconBg: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
      valueColor: 'text-teal-400',
      accentColor: 'text-teal-400'
    },
    cyan: {
      border: 'border-slate-800 hover:border-cyan-500/40',
      iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
      valueColor: 'text-cyan-400',
      accentColor: 'text-cyan-400'
    },
    slate: {
      border: 'border-slate-800 hover:border-slate-700',
      iconBg: 'bg-slate-800 text-slate-400 border-slate-700',
      valueColor: 'text-slate-100',
      accentColor: 'text-slate-400'
    }
  };

  const currentVariant = variantStyles[colorVariant] || variantStyles.blue;

  return (
    <div
      onClick={onClick}
      className={`p-3.5 rounded-xl bg-slate-900/80 border ${currentVariant.border} transition-all duration-150 flex flex-col justify-between ${
        onClick ? 'cursor-pointer hover:bg-slate-850' : ''
      } ${className}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-slate-400 truncate">{title}</span>
        {Icon && (
          <div className={`p-1.5 rounded-lg border ${currentVariant.iconBg}`}>
            <Icon className="h-3.5 w-3.5" />
          </div>
        )}
      </div>

      <div className="mt-2">
        {loading ? (
          <div className="h-6 w-16 bg-slate-800 animate-pulse rounded" />
        ) : (
          <div className="flex items-baseline gap-2">
            <span className={`text-xl font-bold tracking-tight ${currentVariant.valueColor}`}>
              {value}
            </span>
            {badge && (
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                {badge}
              </span>
            )}
          </div>
        )}

        {subtext && (
          <div className="mt-1 text-[11px] text-slate-500 truncate">
            {subtext}
          </div>
        )}

        {trend && (
          <div className="mt-1.5 flex items-center gap-1 text-[10px] font-medium">
            {trend.isPositive ? (
              <span className="text-emerald-400 flex items-center gap-0.5">
                <TrendingUp className="h-3 w-3" />
                <span>{trend.value}</span>
              </span>
            ) : (
              <span className="text-rose-400 flex items-center gap-0.5">
                <TrendingDown className="h-3 w-3" />
                <span>{trend.value}</span>
              </span>
            )}
            {trend.label && <span className="text-slate-500">{trend.label}</span>}
          </div>
        )}
      </div>
    </div>
  );
};
