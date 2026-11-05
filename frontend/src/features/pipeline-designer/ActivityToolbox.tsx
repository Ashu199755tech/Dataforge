import React, { useEffect, useState } from 'react';
import { 
  ArrowRightLeft, 
  FileCode, 
  ShieldCheck, 
  Search, 
  Clock, 
  Variable, 
  GitFork, 
  Globe,
  Cpu,
  Layers,
  Sparkles
} from 'lucide-react';
import api from '../../api/client';

interface DynamicActivity {
  activity_type: string;
  display_name: string;
  category: string;
  description: string;
  icon: string;
}

const DEFAULT_ACTIVITIES = [
  {
    category: 'Move & Transform',
    items: [
      { type: 'CopyData', label: 'Copy Data', icon: ArrowRightLeft, color: 'text-brand-400', desc: 'Stream from source to destination' },
      { type: 'Lookup', label: 'Lookup', icon: Search, color: 'text-teal-400', desc: 'Read dataset or single record' },
      { type: 'DataQualityCheck', label: 'Data Quality', icon: ShieldCheck, color: 'text-purple-400', desc: 'Enforce SLAs and data integrity' },
    ]
  },
  {
    category: 'Control Flow',
    items: [
      { type: 'IfCondition', label: 'If Condition', icon: GitFork, color: 'text-orange-400', desc: 'Evaluate conditions & branch' },
      { type: 'SetVariable', label: 'Set Variable', icon: Variable, color: 'text-cyan-400', desc: 'Dynamically assign pipeline variables' },
      { type: 'Wait', label: 'Wait', icon: Clock, color: 'text-amber-400', desc: 'Pause execution for N seconds' },
    ]
  },
  {
    category: 'Compute & External',
    items: [
      { type: 'SqlScript', label: 'SQL Script', icon: FileCode, color: 'text-emerald-400', desc: 'Execute queries on connection' },
      { type: 'RestApi', label: 'REST API Call', icon: Globe, color: 'text-sky-400', desc: 'Invoke external HTTP webhooks' },
    ]
  }
];

const getIconComponent = (iconName: string) => {
  switch (iconName?.toLowerCase()) {
    case 'arrowrightleft':
      return ArrowRightLeft;
    case 'search':
      return Search;
    case 'shieldcheck':
      return ShieldCheck;
    case 'gitfork':
      return GitFork;
    case 'variable':
      return Variable;
    case 'clock':
      return Clock;
    case 'filecode':
      return FileCode;
    case 'globe':
      return Globe;
    case 'cpu':
      return Cpu;
    default:
      return Layers;
  }
};

const getColorClass = (type: string) => {
  switch (type.toLowerCase()) {
    case 'copydata': return 'text-brand-400';
    case 'lookup': return 'text-teal-400';
    case 'dataqualitycheck': return 'text-purple-400';
    case 'ifcondition': return 'text-orange-400';
    case 'setvariable': return 'text-cyan-400';
    case 'wait': return 'text-amber-400';
    case 'sqlscript': return 'text-emerald-400';
    case 'restapi': return 'text-sky-400';
    default: return 'text-slate-400';
  }
};

export const ActivityToolbox: React.FC = () => {
  const [categories, setCategories] = useState(DEFAULT_ACTIVITIES);

  useEffect(() => {
    const loadDynamicActivities = async () => {
      try {
        const res = await api.get<DynamicActivity[]>('/activities');
        if (res.data && res.data.length > 0) {
          // Group activities by category
          const grouped: Record<string, any[]> = {};
          res.data.forEach((act) => {
            const cat = act.category || 'General';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push({
              type: act.activity_type,
              label: act.display_name,
              icon: getIconComponent(act.icon),
              color: getColorClass(act.activity_type),
              desc: act.description
            });
          });

          const formatted = Object.keys(grouped).map((catName) => ({
            category: catName,
            items: grouped[catName]
          }));

          setCategories(formatted);
        }
      } catch (err) {
        // Fall back gracefully to built-in default catalog
        console.debug('Using local default activity catalogue', err);
      }
    };

    loadDynamicActivities();
  }, []);

  const onDragStart = (event: React.DragEvent, nodeType: string, label: string) => {
    event.dataTransfer.setData('application/reactflow-type', nodeType);
    event.dataTransfer.setData('application/reactflow-label', label);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 p-4 space-y-4 shrink-0 flex flex-col justify-between select-none overflow-y-auto">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Activity Toolbox</h3>
            <p className="text-[11px] text-slate-500">Drag activities onto the canvas</p>
          </div>
          <span className="p-1 rounded bg-brand-500/10 text-brand-400 text-[10px] font-mono border border-brand-500/20 flex items-center gap-1" title="Dynamic Registry Active">
            <Sparkles className="h-3 w-3" />
            <span>Registry</span>
          </span>
        </div>

        {categories.map((cat, idx) => (
          <div key={idx} className="space-y-2">
            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              {cat.category}
            </div>
            <div className="space-y-1.5">
              {cat.items.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, item.type, item.label)}
                    className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/40 cursor-grab active:cursor-grabbing transition space-y-1 group"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className={`h-4 w-4 ${item.color} group-hover:scale-110 transition`} />
                      <span className="text-xs font-semibold text-slate-200">{item.label}</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">{item.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-400">
        <span className="font-semibold text-slate-300">Canvas Tip:</span> Connect handles to build conditional dependency DAGs.
      </div>
    </div>
  );
};
