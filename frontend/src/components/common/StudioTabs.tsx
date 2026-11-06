import React from 'react';
import { LucideIcon } from 'lucide-react';

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  icon?: LucideIcon;
}

interface StudioTabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  variant?: 'pill' | 'underline';
  className?: string;
}

export const StudioTabs: React.FC<StudioTabsProps> = ({
  tabs,
  activeTab,
  onChange,
  variant = 'pill',
  className = ''
}) => {
  if (variant === 'underline') {
    return (
      <div className={`flex items-center gap-4 border-b border-slate-800 ${className}`}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={`flex items-center gap-1.5 pb-2.5 px-1 text-xs font-medium transition-all relative ${
                isActive 
                  ? 'text-white font-semibold' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {Icon && <Icon className={`h-3.5 w-3.5 ${isActive ? 'text-brand-400' : 'text-slate-500'}`} />}
              <span>{tab.label}</span>
              {typeof tab.count === 'number' && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  isActive ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800 text-slate-400'
                }`}>
                  {tab.count}
                </span>
              )}
              {isActive && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-full" />
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-1 bg-slate-950/80 p-0.5 rounded-lg border border-slate-800 ${className}`}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition ${
              isActive 
                ? 'bg-brand-600 text-white shadow-sm' 
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850'
            }`}
          >
            {Icon && <Icon className="h-3 w-3" />}
            <span>{tab.label}</span>
            {typeof tab.count === 'number' && (
              <span className={`text-[10px] px-1 rounded-full font-mono ${
                isActive ? 'bg-brand-700 text-white' : 'bg-slate-800 text-slate-400'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
