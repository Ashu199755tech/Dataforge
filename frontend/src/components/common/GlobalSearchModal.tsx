import React, { useState, useEffect, useRef } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { 
  Search, 
  X, 
  GitBranch, 
  Layers, 
  Database, 
  Clock, 
  ArrowRight,
  Workflow,
  Command,
  Activity
} from 'lucide-react';
import api from '../../api/client';

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SearchItem {
  id: string;
  name: string;
  type: 'Pipeline' | 'Dataset' | 'Connection' | 'Trigger' | 'DataFlow';
  subtext?: string;
  tab: 'pipelines' | 'designer' | 'datasets' | 'connections' | 'triggers' | 'dataflows';
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({ isOpen, onClose }) => {
  const { setCurrentTab, setSelectedPipelineId, activeProject } = useAppStore();
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<SearchItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      loadAllResources();
    } else {
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen, activeProject?.id]);

  const loadAllResources = async () => {
    if (!activeProject?.id) return;
    try {
      const [pipeRes, dsRes, connRes, trigRes, dfRes] = await Promise.allSettled([
        api.get(`/pipelines?project_id=${activeProject.id}`),
        api.get(`/datasets?project_id=${activeProject.id}`),
        api.get(`/connections?project_id=${activeProject.id}`),
        api.get(`/triggers`),
        api.get(`/dataflows?project_id=${activeProject.id}`)
      ]);

      const pool: SearchItem[] = [];

      if (pipeRes.status === 'fulfilled' && Array.isArray(pipeRes.value.data)) {
        pipeRes.value.data.forEach((p: any) => {
          pool.push({
            id: p.id,
            name: p.name,
            type: 'Pipeline',
            subtext: p.description || `${p.definition_json?.activities?.length || 0} activities`,
            tab: 'designer'
          });
        });
      }

      if (dsRes.status === 'fulfilled' && Array.isArray(dsRes.value.data)) {
        dsRes.value.data.forEach((d: any) => {
          pool.push({
            id: d.id,
            name: d.name,
            type: 'Dataset',
            subtext: `${d.dataset_type} • Version ${d.current_version}`,
            tab: 'datasets'
          });
        });
      }

      if (connRes.status === 'fulfilled' && Array.isArray(connRes.value.data)) {
        connRes.value.data.forEach((c: any) => {
          pool.push({
            id: c.id,
            name: c.name,
            type: 'Connection',
            subtext: `${c.connector_type} • ${c.status}`,
            tab: 'connections'
          });
        });
      }

      if (trigRes.status === 'fulfilled' && Array.isArray(trigRes.value.data)) {
        trigRes.value.data.forEach((t: any) => {
          pool.push({
            id: t.id,
            name: t.name,
            type: 'Trigger',
            subtext: `${t.trigger_type} • ${t.is_active ? 'Active' : 'Inactive'}`,
            tab: 'triggers'
          });
        });
      }

      if (dfRes.status === 'fulfilled' && Array.isArray(dfRes.value.data)) {
        dfRes.value.data.forEach((df: any) => {
          pool.push({
            id: df.id,
            name: df.name,
            type: 'DataFlow',
            subtext: df.description || 'Visual ETL graph',
            tab: 'dataflows'
          });
        });
      }

      setItems(pool);
    } catch (e) {
      console.warn('Failed to load search resources', e);
    }
  };

  const filtered = query.trim() === ''
    ? items.slice(0, 8)
    : items.filter(i => 
        i.name.toLowerCase().includes(query.toLowerCase()) || 
        i.type.toLowerCase().includes(query.toLowerCase()) ||
        (i.subtext && i.subtext.toLowerCase().includes(query.toLowerCase()))
      ).slice(0, 15);

  const handleSelect = (item: SearchItem) => {
    if (item.type === 'Pipeline') {
      setSelectedPipelineId(item.id);
      setCurrentTab('designer');
    } else {
      setCurrentTab(item.tab);
    }
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % (filtered.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + (filtered.length || 1)) % (filtered.length || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        handleSelect(filtered[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!isOpen) return null;

  const getTypeIcon = (type: SearchItem['type']) => {
    switch (type) {
      case 'Pipeline': return <GitBranch className="h-4 w-4 text-brand-400" />;
      case 'Dataset': return <Layers className="h-4 w-4 text-purple-400" />;
      case 'Connection': return <Database className="h-4 w-4 text-amber-400" />;
      case 'Trigger': return <Clock className="h-4 w-4 text-emerald-400" />;
      case 'DataFlow': return <Workflow className="h-4 w-4 text-teal-400" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-start justify-center pt-20 px-4">
      <div 
        className="w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-100"
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="relative flex items-center px-4 border-b border-slate-800 bg-slate-950/60">
          <Search className="h-5 w-5 text-slate-400 mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Search pipelines, datasets, connections, triggers, data flows..."
            className="w-full bg-transparent py-4 text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          {query && (
            <button 
              onClick={() => setQuery('')}
              className="p-1 rounded text-slate-400 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400 font-mono ml-2 border border-slate-700">
            ESC
          </span>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-slate-800/40">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              {query ? `No resources matching "${query}"` : 'No resources available in this project'}
            </div>
          ) : (
            filtered.map((item, index) => {
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={`${item.type}-${item.id}`}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition text-xs ${
                    isSelected 
                      ? 'bg-brand-600/20 text-white border border-brand-500/30' 
                      : 'text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-1.5 rounded-md bg-slate-800/90 border border-slate-700/50">
                      {getTypeIcon(item.type)}
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-slate-200 truncate flex items-center gap-2">
                        <span>{item.name}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                          {item.type}
                        </span>
                      </div>
                      {item.subtext && (
                        <div className="text-[11px] text-slate-400 truncate">
                          {item.subtext}
                        </div>
                      )}
                    </div>
                  </div>
                  <ArrowRight className={`h-4 w-4 shrink-0 transition ${isSelected ? 'text-brand-400 translate-x-0.5' : 'text-slate-600'}`} />
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-4 py-2 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between text-[11px] text-slate-500">
          <div className="flex items-center gap-3">
            <span>Use <kbd className="px-1 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-mono text-[10px]">↑</kbd> <kbd className="px-1 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-mono text-[10px]">↓</kbd> to navigate</span>
            <span><kbd className="px-1 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-mono text-[10px]">↵</kbd> to select</span>
          </div>
          <div className="font-mono text-[10px]">DataForge OmniSearch</div>
        </div>
      </div>
    </div>
  );
};
