import React from 'react';
import { ArrowRightLeft, FileCode, ShieldCheck, Filter, Clock, GitMerge } from 'lucide-react';

export const ActivityToolbox: React.FC = () => {
  const onDragStart = (event: React.DragEvent, nodeType: string, label: string) => {
    event.dataTransfer.setData('application/reactflow-type', nodeType);
    event.dataTransfer.setData('application/reactflow-label', label);
    event.dataTransfer.effectAllowed = 'move';
  };

  const activities = [
    {
      category: 'Move & Transform',
      items: [
        { type: 'CopyData', label: 'Copy Data', icon: ArrowRightLeft, color: 'text-brand-400', desc: 'Stream from source to destination' },
        { type: 'DataQualityCheck', label: 'Data Quality', icon: ShieldCheck, color: 'text-purple-400', desc: 'Enforce SLAs and data integrity' },
      ]
    },
    {
      category: 'Compute & Scripts',
      items: [
        { type: 'SqlScript', label: 'SQL Script', icon: FileCode, color: 'text-emerald-400', desc: 'Execute queries on connection' },
      ]
    }
  ];

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 p-4 space-y-4 shrink-0 flex flex-col justify-between select-none">
      <div className="space-y-4">
        <div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">Activity Toolbox</h3>
          <p className="text-[11px] text-slate-500">Drag activities onto the canvas</p>
        </div>

        {activities.map((cat, idx) => (
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
        <span className="font-semibold text-slate-300">Canvas Tip:</span> Drag handle points between activities to establish topological DAG dependencies.
      </div>
    </div>
  );
};
