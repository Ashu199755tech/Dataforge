import React from 'react';
import { useAppStore } from '../../store/useAppStore';
import { Database, ShieldCheck, Activity, Bell, Layers, Cpu } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { activeWorkspace, activeProject } = useAppStore();

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-4 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-brand-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
          <Layers className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="font-bold text-base tracking-tight text-white flex items-center gap-2">
            DataFlow <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400 font-semibold border border-brand-500/30">Enterprise</span>
          </span>
        </div>

        <div className="h-5 w-[1px] bg-slate-800 mx-2" />

        {/* Workspace & Project Selector Display */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="bg-slate-800/80 px-2 py-1 rounded text-slate-300 font-medium border border-slate-700/50">
            {activeWorkspace?.name || 'Enterprise Workspace'}
          </span>
          <span>/</span>
          <span className="text-brand-400 font-medium">
            {activeProject?.name || 'Analytics Project'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs">
        {/* System Engine Status */}
        <div className="flex items-center gap-2 bg-emerald-500/10 text-emerald-400 px-2.5 py-1 rounded-full border border-emerald-500/20">
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-medium">Engine: Online</span>
        </div>

        <div className="flex items-center gap-2 bg-slate-800/70 text-slate-300 px-2.5 py-1 rounded border border-slate-700/50">
          <Cpu className="h-3.5 w-3.5 text-brand-400" />
          <span>Worker Pool: 4 Active</span>
        </div>

        <div className="flex items-center gap-2 border-l border-slate-800 pl-4">
          <div className="h-7 w-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300">
            A
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-slate-200 font-medium">Admin</div>
            <div className="text-[10px] text-slate-500">Platform Engineer</div>
          </div>
        </div>
      </div>
    </header>
  );
};
