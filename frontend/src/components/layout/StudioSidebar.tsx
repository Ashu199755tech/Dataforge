import React, { useState } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { 
  Home,
  GitBranch, 
  Workflow, 
  Database, 
  Layers, 
  Clock, 
  PlayCircle, 
  Activity, 
  Bell, 
  Cpu, 
  Rocket, 
  Network, 
  ShieldCheck, 
  ChevronLeft, 
  ChevronRight,
  Sliders,
  FolderKanban,
  FileText,
  Info
} from 'lucide-react';

interface NavItem {
  id: 'dashboard' | 'pipelines' | 'designer' | 'dataflows' | 'connections' | 'datasets' | 'triggers' | 'runs' | 'dq' | 'runtimes' | 'deployments' | 'lineage' | 'observability';
  label: string;
  icon: React.ElementType;
  badge?: string;
}

interface NavGroup {
  groupName: string;
  items: NavItem[];
}

export const StudioSidebar: React.FC = () => {
  const { currentTab, setCurrentTab, setSelectedPipelineId, isSidebarCollapsed, toggleSidebar } = useAppStore();
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  const navGroups: NavGroup[] = [
    {
      groupName: 'Author',
      items: [
        { id: 'pipelines', label: 'Pipelines', icon: GitBranch },
        { id: 'dataflows', label: 'Data Flows', icon: Workflow },
        { id: 'datasets', label: 'Datasets', icon: Layers },
        { id: 'connections', label: 'Connections', icon: Database },
        { id: 'triggers', label: 'Triggers', icon: Clock },
      ]
    },
    {
      groupName: 'Monitor',
      items: [
        { id: 'runs', label: 'Pipeline Runs', icon: PlayCircle },
        { id: 'observability', label: 'Fleet & Alerts', icon: Activity },
      ]
    },
    {
      groupName: 'Manage',
      items: [
        { id: 'runtimes', label: 'Runtime Manager', icon: Cpu },
        { id: 'deployments', label: 'Deployments & CI/CD', icon: Rocket },
      ]
    },
    {
      groupName: 'Governance',
      items: [
        { id: 'lineage', label: 'Data Lineage', icon: Network },
        { id: 'dq', label: 'Data Quality', icon: ShieldCheck },
      ]
    }
  ];

  const handleNavClick = (id: any) => {
    if (id === 'pipelines') {
      setSelectedPipelineId(null);
    }
    setCurrentTab(id);
  };

  const isItemActive = (id: string) => {
    if (id === currentTab) return true;
    if (id === 'pipelines' && currentTab === 'designer') return true;
    return false;
  };

  return (
    <aside 
      className={`bg-slate-900/90 border-r border-slate-800 flex flex-col justify-between select-none shrink-0 transition-all duration-200 z-30 relative ${
        isSidebarCollapsed ? 'w-12' : 'w-56'
      }`}
    >
      {/* Navigation Items Area */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-2 space-y-4">
        
        {/* Workspace Home / Studio Hub Item */}
        <div className="px-1.5">
          <div className="relative">
            <button
              onClick={() => handleNavClick('dashboard')}
              onMouseEnter={() => setHoveredItem('dashboard')}
              onMouseLeave={() => setHoveredItem(null)}
              className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-xs font-medium transition-all ${
                currentTab === 'dashboard'
                  ? 'bg-brand-600/20 text-brand-300 font-semibold border-l-2 border-brand-400'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Home className={`h-4 w-4 shrink-0 ${currentTab === 'dashboard' ? 'text-brand-400' : 'text-slate-400'}`} />
              {!isSidebarCollapsed && <span className="truncate">Home Workspace</span>}
            </button>

            {/* Floating Tooltip when collapsed */}
            {isSidebarCollapsed && hoveredItem === 'dashboard' && (
              <div className="fixed left-14 z-50 px-2.5 py-1 bg-slate-900 border border-slate-700 text-xs rounded shadow-2xl whitespace-nowrap text-white font-medium pointer-events-none">
                Home Workspace
              </div>
            )}
          </div>
        </div>

        {/* ADF-Inspired Functional Groups */}
        {navGroups.map((group) => (
          <div key={group.groupName} className="px-1.5 space-y-1">
            {/* Category Header */}
            {!isSidebarCollapsed ? (
              <div className="px-2.5 pt-1 pb-1 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                {group.groupName}
              </div>
            ) : (
              <div className="my-1 border-t border-slate-800/80 mx-1" />
            )}

            {/* Group Items */}
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = isItemActive(item.id);

              return (
                <div key={item.id} className="relative">
                  <button
                    onClick={() => handleNavClick(item.id)}
                    onMouseEnter={() => setHoveredItem(item.id)}
                    onMouseLeave={() => setHoveredItem(null)}
                    className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-xs font-medium transition-all ${
                      active
                        ? 'bg-brand-600/20 text-brand-300 font-semibold border-l-2 border-brand-400 shadow-sm'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-brand-400' : 'text-slate-400'}`} />
                    {!isSidebarCollapsed && (
                      <span className="truncate flex-1 text-left">{item.label}</span>
                    )}
                  </button>

                  {/* Floating Tooltip when collapsed */}
                  {isSidebarCollapsed && hoveredItem === item.id && (
                    <div className="fixed left-14 z-50 px-2.5 py-1 bg-slate-900 border border-slate-700 text-xs rounded shadow-2xl whitespace-nowrap text-white font-medium flex items-center gap-2 pointer-events-none">
                      <span className="text-[10px] text-slate-400 uppercase font-mono">{group.groupName} /</span>
                      <span>{item.label}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Sidebar Footer with Collapse/Expand Toggle */}
      <div className="p-2 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
        {!isSidebarCollapsed && (
          <div className="text-[10px] text-slate-500 font-mono truncate px-1">
            DataForge v1.0 Enterprise
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition ml-auto"
          title={isSidebarCollapsed ? 'Expand Navigation Rail' : 'Collapse Navigation Rail'}
        >
          {isSidebarCollapsed ? (
            <ChevronRight className="h-4 w-4 text-brand-400" />
          ) : (
            <ChevronLeft className="h-4 w-4 text-slate-400" />
          )}
        </button>
      </div>
    </aside>
  );
};
