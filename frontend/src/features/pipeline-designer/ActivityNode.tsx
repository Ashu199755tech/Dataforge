import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { 
  ArrowRightLeft, 
  FileCode, 
  ShieldCheck, 
  Layers, 
  Search, 
  Variable, 
  Clock, 
  GitFork, 
  Globe,
  Ban,
  Trash2,
  X,
  FileSearch,
  Database,
  Repeat,
  Workflow,
  Split,
  Filter,
  AlertOctagon,
  ListPlus,
  RotateCw
} from 'lucide-react';

export const ActivityNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const activityData = data as {
    label: string;
    activityType: string;
    status?: string;
    state?: 'Active' | 'Disabled';
    config?: any;
    retry_policy?: {
      max_retries: number;
      retry_interval_seconds: number;
    };
    onDelete?: (id: string) => void;
  };

  const isDeactivated = activityData.state === 'Disabled';

  const getIcon = () => {
    switch (activityData.activityType) {
      case 'CopyData':
        return <ArrowRightLeft className="h-4 w-4 text-brand-400" />;
      case 'SqlScript':
        return <FileCode className="h-4 w-4 text-emerald-400" />;
      case 'DataQualityCheck':
        return <ShieldCheck className="h-4 w-4 text-purple-400" />;
      case 'Lookup':
        return <Search className="h-4 w-4 text-teal-400" />;
      case 'SetVariable':
        return <Variable className="h-4 w-4 text-cyan-400" />;
      case 'Wait':
        return <Clock className="h-4 w-4 text-amber-400" />;
      case 'IfCondition':
        return <GitFork className="h-4 w-4 text-orange-400" />;
      case 'RestApi':
        return <Globe className="h-4 w-4 text-sky-400" />;
      case 'GetMetadata':
        return <FileSearch className="h-4 w-4 text-indigo-400" />;
      case 'DeleteData':
        return <Trash2 className="h-4 w-4 text-rose-400" />;
      case 'ForEach':
        return <Repeat className="h-4 w-4 text-emerald-400" />;
      case 'ExecutePipeline':
        return <Workflow className="h-4 w-4 text-violet-400" />;
      case 'Switch':
        return <Split className="h-4 w-4 text-yellow-400" />;
      case 'Filter':
        return <Filter className="h-4 w-4 text-blue-400" />;
      case 'Fail':
        return <AlertOctagon className="h-4 w-4 text-red-500" />;
      case 'AppendVariable':
        return <ListPlus className="h-4 w-4 text-cyan-400" />;
      case 'Until':
        return <RotateCw className="h-4 w-4 text-pink-400" />;
      default:
        return <Layers className="h-4 w-4 text-slate-400" />;
    }
  };

  const getBorderColor = () => {
    if (selected) return 'border-brand-500 shadow-xl shadow-brand-500/20 ring-2 ring-brand-500/40';
    if (isDeactivated) return 'border-dashed border-slate-700 opacity-60';
    return 'border-slate-700/80 hover:border-slate-500';
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (activityData.onDelete) {
      activityData.onDelete(id);
    }
  };

  return (
    <div className={`p-3.5 rounded-xl bg-slate-900/95 border ${getBorderColor()} min-w-[240px] max-w-[280px] shadow-lg transition duration-150 relative text-xs select-none backdrop-blur-sm group`}>
      {/* Floating Action Pill on Selection */}
      {selected && (
        <div className="absolute -top-7 right-2 flex items-center gap-1 z-30">
          <button
            onClick={handleDelete}
            className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[10px] shadow-md transition"
            title="Delete activity"
          >
            <Trash2 className="h-3 w-3" />
            <span>Delete</span>
          </button>
        </div>
      )}

      {/* Target input handle on Left */}
      <Handle
        type="target"
        position={Position.Left}
        id="input"
        className="!w-3 !h-3 !bg-slate-300 !border-2 !border-slate-900 !rounded-full hover:!scale-125 transition"
        title="Input Dependency"
      />

      {/* Node Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-slate-800 border border-slate-700/70 shrink-0">
            {getIcon()}
          </div>
          <div>
            <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider font-semibold">
              {activityData.activityType}
            </div>
            <div className="font-semibold text-slate-200 truncate max-w-[130px]">
              {activityData.label}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {isDeactivated ? (
            <span className="px-1.5 py-0.5 rounded text-[9px] bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1">
              <Ban className="h-2.5 w-2.5 text-amber-400" />
              <span>Disabled</span>
            </span>
          ) : (
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" title="Active" />
          )}

          {/* Direct Cross / Delete Button */}
          <button
            onClick={handleDelete}
            className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition"
            title="Delete Activity"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Node Body Details Preview */}
      <div className="py-2 space-y-1 text-[11px] font-mono text-slate-400">
        {activityData.config?.source?.table_name && activityData.config?.destination?.table_name && (
          <div className="truncate flex items-center gap-1 text-[10px]">
            <span className="text-slate-300">{activityData.config.source.table_name}</span>
            <span className="text-brand-400 font-bold">→</span>
            <span className="text-slate-300">{activityData.config.destination.table_name}</span>
          </div>
        )}

        {activityData.config?.expression && (
          <div className="truncate text-amber-400/90 text-[10px]">
            {activityData.config.expression}
          </div>
        )}

        {activityData.config?.variable_name && (
          <div className="truncate text-cyan-400/90 text-[10px]">
            {activityData.config.variable_name} = {activityData.config.value}
          </div>
        )}

        {activityData.config?.url && (
          <div className="truncate text-sky-400 text-[10px]">
            {activityData.config.method || 'GET'} {activityData.config.url}
          </div>
        )}

        {activityData.config?.wait_time_in_seconds && (
          <div className="text-amber-300 text-[10px]">
            Wait: {activityData.config.wait_time_in_seconds}s
          </div>
        )}

        {activityData.activityType === 'GetMetadata' && activityData.config?.table_name && (
          <div className="truncate text-indigo-400 text-[10px] flex items-center gap-1">
            <span className="text-slate-500">Inspect:</span>
            <span className="font-semibold">{activityData.config.table_name}</span>
          </div>
        )}

        {activityData.activityType === 'DeleteData' && activityData.config?.table_name && (
          <div className="truncate text-rose-400 text-[10px] flex items-center gap-1">
            <span className="text-slate-500">{activityData.config.delete_mode === 'truncate' ? 'Truncate:' : 'Delete:'}</span>
            <span className="font-semibold">{activityData.config.table_name}</span>
          </div>
        )}

        {activityData.activityType === 'ForEach' && (
          <div className="truncate text-emerald-400 text-[10px] flex items-center gap-1">
            <span className="text-slate-500">Loop:</span>
            <span className="font-semibold font-mono">{activityData.config?.is_sequential ? 'Sequential' : 'Parallel'}</span>
          </div>
        )}

        {activityData.activityType === 'ExecutePipeline' && (
          <div className="truncate text-violet-400 text-[10px] flex items-center gap-1">
            <span className="text-slate-500">Child:</span>
            <span className="font-semibold font-mono">{activityData.config?.pipeline_name || activityData.config?.pipeline_id || 'Target Pipeline'}</span>
          </div>
        )}

        {activityData.activityType === 'Switch' && activityData.config?.expression && (
          <div className="truncate text-yellow-400 text-[10px] flex items-center gap-1">
            <span className="text-slate-500">Switch:</span>
            <span className="font-mono truncate">{activityData.config.expression}</span>
          </div>
        )}

        {activityData.activityType === 'Filter' && (
          <div className="truncate text-blue-400 text-[10px] flex items-center gap-1">
            <span className="text-slate-500">Filter:</span>
            <span className="font-mono truncate">{activityData.config?.condition}</span>
          </div>
        )}

        {activityData.activityType === 'Fail' && (
          <div className="truncate text-red-400 text-[10px] flex items-center gap-1 font-semibold">
            <span>Fail:</span>
            <span className="truncate">{activityData.config?.message || 'Deliberate Error'}</span>
          </div>
        )}

        {activityData.activityType === 'AppendVariable' && activityData.config?.variable_name && (
          <div className="truncate text-cyan-400 text-[10px] flex items-center gap-1 font-mono">
            <span className="text-slate-500">Append:</span>
            <span className="truncate">{activityData.config.variable_name}</span>
          </div>
        )}

        {activityData.activityType === 'Until' && activityData.config?.expression && (
          <div className="truncate text-pink-400 text-[10px] flex items-center gap-1 font-mono">
            <span className="text-slate-500">Until:</span>
            <span className="truncate">{activityData.config.expression}</span>
          </div>
        )}
      </div>

      {/* ADF-Style Multi-Output Ports (Success, Failure, Completion, Skip) */}
      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400">
        <span className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Outcomes</span>
        <div className="flex items-center gap-2">
          {/* Green: Success */}
          <div className="flex items-center gap-1" title="Upon Success (Green)">
            <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
            <span className="text-[9px] text-emerald-400 font-medium">OK</span>
          </div>
          {/* Red: Failure */}
          <div className="flex items-center gap-1" title="Upon Failure (Red)">
            <span className="h-2 w-2 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50" />
            <span className="text-[9px] text-rose-400 font-medium">Fail</span>
          </div>
          {/* Blue: Completion */}
          <div className="flex items-center gap-1" title="Upon Completion (Blue)">
            <span className="h-2 w-2 rounded-full bg-blue-500 shadow-sm shadow-blue-500/50" />
            <span className="text-[9px] text-blue-400 font-medium">Done</span>
          </div>
          {/* Gray: Skip */}
          <div className="flex items-center gap-1" title="Upon Skip (Gray)">
            <span className="h-2 w-2 rounded-full bg-slate-400 shadow-sm shadow-slate-400/50" />
            <span className="text-[9px] text-slate-400 font-medium">Skip</span>
          </div>
        </div>
      </div>

      {/* Output Handles aligned on the Right */}
      {/* 1. Success (Green) */}
      <Handle
        type="source"
        position={Position.Right}
        id="success"
        style={{ top: '22%', background: '#10b981', width: '10px', height: '10px', right: '-6px' }}
        className="!border-2 !border-slate-900 hover:!scale-150 transition"
        title="Upon Success (Succeeded)"
      />

      {/* 2. Failure (Red) */}
      <Handle
        type="source"
        position={Position.Right}
        id="failure"
        style={{ top: '44%', background: '#ef4444', width: '10px', height: '10px', right: '-6px' }}
        className="!border-2 !border-slate-900 hover:!scale-150 transition"
        title="Upon Failure (Failed)"
      />

      {/* 3. Completion (Blue) */}
      <Handle
        type="source"
        position={Position.Right}
        id="completion"
        style={{ top: '66%', background: '#3b82f6', width: '10px', height: '10px', right: '-6px' }}
        className="!border-2 !border-slate-900 hover:!scale-150 transition"
        title="Upon Completion (Completed)"
      />

      {/* 4. Skipped (Gray) */}
      <Handle
        type="source"
        position={Position.Right}
        id="skipped"
        style={{ top: '88%', background: '#94a3b8', width: '10px', height: '10px', right: '-6px' }}
        className="!border-2 !border-slate-900 hover:!scale-150 transition"
        title="Upon Skip (Skipped)"
      />
    </div>
  );
};
