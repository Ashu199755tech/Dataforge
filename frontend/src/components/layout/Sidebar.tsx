import React from 'react';
import { useAppStore } from '../../store/useAppStore';
import { 
  LayoutDashboard, 
  GitBranch, 
  Database, 
  Activity, 
  ShieldCheck, 
  PlayCircle,
  FileText
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { currentTab, setCurrentTab, setSelectedPipelineId } = useAppStore();

  const navItems = [
    { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
    { id: 'pipelines', label: 'Pipelines', icon: GitBranch },
    { id: 'connections', label: 'Connections', icon: Database },
    { id: 'runs', label: 'Runs & Monitor', icon: PlayCircle },
    { id: 'dq', label: 'Data Quality', icon: ShieldCheck },
  ];

  const handleNavClick = (id: any) => {
    if (id === 'pipelines') {
      setSelectedPipelineId(null);
    }
    setCurrentTab(id);
  };

  return (
    <aside className="w-56 bg-slate-900/60 border-r border-slate-800 flex flex-col justify-between py-3 shrink-0">
      <div className="space-y-1 px-2">
        <div className="px-3 pb-2 pt-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          Platform Modules
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id || (item.id === 'pipelines' && currentTab === 'designer');
          return (
            <button
              key={item.id}
              onClick={() => handleNavClick(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? 'text-brand-400' : 'text-slate-500'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      <div className="px-3 pt-4 border-t border-slate-800 text-[11px] text-slate-500 space-y-1">
        <div className="flex items-center justify-between text-slate-400">
          <span>Version</span>
          <span className="font-mono text-slate-400">1.0.0-mvp</span>
        </div>
        <div className="text-[10px] text-slate-600">
          Clean-room Enterprise Core
        </div>
      </div>
    </aside>
  );
};
