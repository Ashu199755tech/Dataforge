import React from 'react';
import { 
  Database, 
  Table, 
  Sliders, 
  Filter, 
  PlusCircle, 
  ArrowDownAZ, 
  Sigma, 
  GitMerge, 
  Layers, 
  Key, 
  Split, 
  Search 
} from 'lucide-react';

const OPERATORS = [
  {
    category: 'Inputs & Outputs',
    items: [
      { type: 'Source', label: 'Source', icon: Database, color: 'text-emerald-400', desc: 'Read database or file stream' },
      { type: 'Sink', label: 'Sink', icon: Table, color: 'text-rose-400', desc: 'Write output to target warehouse/file' }
    ]
  },
  {
    category: 'Schema & Column Modifiers',
    items: [
      { type: 'Select', label: 'Select / Rename', icon: Sliders, color: 'text-blue-400', desc: 'Project, rename, or drop columns' },
      { type: 'DerivedColumn', label: 'Derived Column', icon: PlusCircle, color: 'text-purple-400', desc: 'Compute formulas or append columns' },
      { type: 'SurrogateKey', label: 'Surrogate Key', icon: Key, color: 'text-yellow-400', desc: 'Generate incremental integer keys' }
    ]
  },
  {
    category: 'Row Operations',
    items: [
      { type: 'Filter', label: 'Filter', icon: Filter, color: 'text-amber-400', desc: 'Filter rows by boolean predicate' },
      { type: 'Sort', label: 'Sort', icon: ArrowDownAZ, color: 'text-cyan-400', desc: 'Order rows by specified columns' },
      { type: 'ConditionalSplit', label: 'Conditional Split', icon: Split, color: 'text-red-400', desc: 'Branch stream by conditions' }
    ]
  },
  {
    category: 'Multi-Stream & Joins',
    items: [
      { type: 'Join', label: 'Join', icon: GitMerge, color: 'text-pink-400', desc: 'Inner, left, outer join 2 streams' },
      { type: 'Union', label: 'Union', icon: Layers, color: 'text-indigo-400', desc: 'Stack and combine rows from streams' },
      { type: 'Lookup', label: 'Lookup', icon: Search, color: 'text-sky-400', desc: 'Enrich stream with secondary lookup' }
    ]
  },
  {
    category: 'Aggregates & Reshape',
    items: [
      { type: 'Aggregate', label: 'Aggregate', icon: Sigma, color: 'text-orange-400', desc: 'Group by & calculate sum, avg, count' },
      { type: 'Window', label: 'Window', icon: Table, color: 'text-teal-400', desc: 'Row numbers, ranks, and cumsums' }
    ]
  }
];

export const DataFlowToolbox: React.FC = () => {
  const onDragStart = (event: React.DragEvent, nodeType: string, label: string) => {
    event.dataTransfer.setData('application/dataflow-operator', JSON.stringify({ nodeType, label }));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-full overflow-hidden select-none shrink-0">
      <div className="p-3 border-b border-slate-800">
        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
          Transformation Palette
        </h3>
        <p className="text-[11px] text-slate-500 mt-0.5">
          Drag operators onto the transformation canvas
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-2.5 space-y-4">
        {OPERATORS.map((group) => (
          <div key={group.category} className="space-y-1.5">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-1">
              {group.category}
            </span>
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, item.type, item.label)}
                    className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg bg-slate-950/70 border border-slate-800/80 hover:border-brand-500/50 hover:bg-slate-800/60 cursor-grab active:cursor-grabbing transition group"
                  >
                    <div className="p-1 rounded bg-slate-900 border border-slate-800 shrink-0">
                      <Icon className={`h-3.5 w-3.5 ${item.color}`} />
                    </div>
                    <div className="truncate">
                      <div className="text-xs font-semibold text-slate-200 group-hover:text-brand-400 transition">
                        {item.label}
                      </div>
                      <div className="text-[10px] text-slate-500 truncate">
                        {item.desc}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
