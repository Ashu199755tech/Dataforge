import React from 'react';
import { LucideIcon, ArrowRight } from 'lucide-react';

export type ActionAccent = 'blue' | 'teal' | 'amber' | 'purple' | 'emerald' | 'indigo';

interface QuickActionCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  actionLabel?: string;
  badge?: string;
  accentColor?: ActionAccent;
  onClick: () => void;
  className?: string;
}

export const QuickActionCard: React.FC<QuickActionCardProps> = ({
  title,
  description,
  icon: Icon,
  actionLabel = 'Get started',
  badge,
  accentColor = 'blue',
  onClick,
  className = ''
}) => {
  const accentStyles = {
    blue: {
      border: 'hover:border-brand-500/50',
      iconBg: 'bg-blue-500/10 text-blue-400 border-blue-500/20 group-hover:bg-blue-500/20',
      titleHover: 'group-hover:text-brand-300',
      labelColor: 'text-brand-400'
    },
    teal: {
      border: 'hover:border-teal-500/50',
      iconBg: 'bg-teal-500/10 text-teal-400 border-teal-500/20 group-hover:bg-teal-500/20',
      titleHover: 'group-hover:text-teal-300',
      labelColor: 'text-teal-400'
    },
    amber: {
      border: 'hover:border-amber-500/50',
      iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20 group-hover:bg-amber-500/20',
      titleHover: 'group-hover:text-amber-300',
      labelColor: 'text-amber-400'
    },
    purple: {
      border: 'hover:border-purple-500/50',
      iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20 group-hover:bg-purple-500/20',
      titleHover: 'group-hover:text-purple-300',
      labelColor: 'text-purple-400'
    },
    emerald: {
      border: 'hover:border-emerald-500/50',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 group-hover:bg-emerald-500/20',
      titleHover: 'group-hover:text-emerald-300',
      labelColor: 'text-emerald-400'
    },
    indigo: {
      border: 'hover:border-indigo-500/50',
      iconBg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20 group-hover:bg-indigo-500/20',
      titleHover: 'group-hover:text-indigo-300',
      labelColor: 'text-indigo-400'
    }
  };

  const currentAccent = accentStyles[accentColor] || accentStyles.blue;

  return (
    <div
      onClick={onClick}
      className={`group p-3.5 rounded-xl bg-slate-900/80 hover:bg-slate-850 border border-slate-800 ${currentAccent.border} cursor-pointer transition-all duration-150 flex flex-col justify-between shadow-sm select-none ${className}`}
    >
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <div className={`h-8 w-8 rounded-lg border flex items-center justify-center transition ${currentAccent.iconBg}`}>
            <Icon className="h-4 w-4" />
          </div>
          {badge && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
              {badge}
            </span>
          )}
        </div>

        <div className={`text-xs font-semibold text-white ${currentAccent.titleHover} transition`}>
          {title}
        </div>
        <div className="text-[11px] text-slate-400 mt-1 line-clamp-2">
          {description}
        </div>
      </div>

      <div className={`mt-3 flex items-center text-[10px] ${currentAccent.labelColor} font-medium group-hover:translate-x-0.5 transition-transform gap-1`}>
        <span>{actionLabel}</span>
        <ArrowRight className="h-3 w-3" />
      </div>
    </div>
  );
};
