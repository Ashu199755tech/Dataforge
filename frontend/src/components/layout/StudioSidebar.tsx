import React, { useState, useMemo } from 'react';
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
  Info,
  CreditCard,
  Search,
  X
} from 'lucide-react';

interface NavItem {
  id: 'dashboard' | 'pipelines' | 'designer' | 'dataflows' | 'connections' | 'datasets' | 'triggers' | 'runs' | 'dq' | 'runtimes' | 'deployments' | 'lineage' | 'observability' | 'billing';
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
  const [sidebarSearchQuery, setSidebarSearchQuery] = useState('');

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
        { id: 'billing', label: 'Billing & Cost Management', icon: CreditCard },
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

  const filteredNavGroups = useMemo(() => {
    if (!sidebarSearchQuery.trim()) return navGroups;
    const q = sidebarSearchQuery.toLowerCase().trim();
    return navGroups
      .map(group => ({
        ...group,
        items: group.items.filter(item => 
          item.label.toLowerCase().includes(q) || group.groupName.toLowerCase().includes(q)
        )
      }))
      .filter(group => group.items.length > 0);
  }, [navGroups, sidebarSearchQuery]);

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
      className={`bg-slate-900/90 border-r border-slate-800 flex flex-col justify-between select-none shrink-0 h-full min-h-0 max-h-full transition-all duration-200 z-30 relative ${
        isSidebarCollapsed ? 'w-12' : 'w-56'
      }`}
    >
      {/* Navigation Items Area */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-2 space-y-3">
        
        {/* Navigation Tab Search Input */}
        {!isSidebarCollapsed ? (
          <div className="px-2 pt-0.5">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              <input
                type="text"
                placeholder="Search tabs..."
                value={sidebarSearchQuery}
                onChange={(e) => setSidebarSearchQuery(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-8 pr-7 py-1.5 text-[11px] text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500 transition shadow-inner"
              />
              {sidebarSearchQuery && (
                <button
                  onClick={() => setSidebarSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  title="Clear search"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="px-1.5 pt-0.5 flex justify-center">
            <button
              onClick={() => toggleSidebar()}
              title="Search navigation tabs"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition"
            >
              <Search className="w-4 h-4 text-slate-400 hover:text-brand-400" />
            </button>
          </div>
        )}

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
        {filteredNavGroups.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-slate-500">
            No tabs match "{sidebarSearchQuery}"
            <button
              onClick={() => setSidebarSearchQuery('')}
              className="block mx-auto mt-2 text-[11px] text-brand-400 hover:underline"
            >
              Clear filter
            </button>
          </div>
        ) : (
          filteredNavGroups.map((group) => (
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
          ))
        )}
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
