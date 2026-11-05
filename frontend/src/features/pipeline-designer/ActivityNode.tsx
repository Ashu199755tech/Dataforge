import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { ArrowRightLeft, FileCode, ShieldCheck, Layers } from 'lucide-react';

export const ActivityNode: React.FC<NodeProps> = ({ data, selected }) => {
  const activityData = data as {
    label: string;
    activityType: 'CopyData' | 'SqlScript' | 'DataQualityCheck' | string;
    status?: string;
    config?: any;
  };

  const getIcon = () => {
    switch (activityData.activityType) {
      case 'CopyData':
        return <ArrowRightLeft className="h-4 w-4 text-brand-400" />;
      case 'SqlScript':
        return <FileCode className="h-4 w-4 text-emerald-400" />;
      case 'DataQualityCheck':
        return <ShieldCheck className="h-4 w-4 text-purple-400" />;
      default:
        return <Layers className="h-4 w-4 text-amber-400" />;
    }
  };

  const getBorderColor = () => {
    if (selected) return 'border-brand-500 shadow-lg shadow-brand-500/20 ring-2 ring-brand-500/30';
    return 'border-slate-700/80 hover:border-slate-500';
  };

  return (
    <div className={`px-4 py-3 rounded-xl bg-slate-900 border ${getBorderColor()} min-w-[200px] transition duration-150`}>
      <Handle type="target" position={Position.Left} className="!bg-brand-400" />
      
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-slate-800/90 border border-slate-700/60 shrink-0">
          {getIcon()}
        </div>
        <div className="overflow-hidden">
          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
            {activityData.activityType}
          </div>
          <div className="text-xs font-semibold text-slate-200 truncate">
            {activityData.label}
          </div>
        </div>
      </div>

      {activityData.config?.source?.table_name && activityData.config?.destination?.table_name && (
        <div className="mt-2 pt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-400 truncate flex items-center gap-1">
          <span className="text-slate-300">{activityData.config.source.table_name}</span>
          <span className="text-brand-400">→</span>
          <span className="text-slate-300">{activityData.config.destination.table_name}</span>
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-brand-400" />
    </div>
  );
};
