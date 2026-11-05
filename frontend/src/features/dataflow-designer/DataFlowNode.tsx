import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { 
  Database, 
  ArrowRightLeft, 
  Filter, 
  Sliders, 
  PlusCircle, 
  ArrowDownAZ, 
  Sigma, 
  GitMerge, 
  Layers, 
  Key, 
  Table, 
  Split, 
  Search,
  Eye,
  Trash2,
  X
} from 'lucide-react';

export const DataFlowNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const nodeData = data as {
    label: string;
    operatorType: string;
    config?: any;
    onDelete?: (id: string) => void;
    onPreview?: (id: string) => void;
  };

  const opType = nodeData.operatorType || 'Select';

  const getIcon = () => {
    switch (opType) {
      case 'Source':
        return <Database className="h-4 w-4 text-emerald-400" />;
      case 'Sink':
        return <Table className="h-4 w-4 text-rose-400" />;
      case 'Select':
        return <Sliders className="h-4 w-4 text-blue-400" />;
      case 'Filter':
        return <Filter className="h-4 w-4 text-amber-400" />;
      case 'DerivedColumn':
        return <PlusCircle className="h-4 w-4 text-purple-400" />;
      case 'Sort':
        return <ArrowDownAZ className="h-4 w-4 text-cyan-400" />;
      case 'Aggregate':
        return <Sigma className="h-4 w-4 text-orange-400" />;
      case 'Join':
        return <GitMerge className="h-4 w-4 text-pink-400" />;
      case 'Union':
        return <Layers className="h-4 w-4 text-indigo-400" />;
      case 'SurrogateKey':
        return <Key className="h-4 w-4 text-yellow-400" />;
      case 'Window':
        return <Table className="h-4 w-4 text-teal-400" />;
      case 'ConditionalSplit':
        return <Split className="h-4 w-4 text-red-400" />;
      case 'Lookup':
        return <Search className="h-4 w-4 text-sky-400" />;
      default:
        return <Sliders className="h-4 w-4 text-slate-400" />;
    }
  };

  const getBorderColor = () => {
    if (selected) return 'border-brand-500 shadow-xl shadow-brand-500/25 ring-2 ring-brand-500/40';
    return 'border-slate-800 hover:border-slate-600';
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (nodeData.onDelete) {
      nodeData.onDelete(id);
    }
  };

  const handlePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (nodeData.onPreview) {
      nodeData.onPreview(id);
    }
  };

  const isMultiInput = ['Join', 'Lookup', 'Union'].includes(opType);
  const isSource = opType === 'Source';
  const isSink = opType === 'Sink';

  return (
    <div className={`p-3 rounded-xl bg-slate-900/95 border ${getBorderColor()} min-w-[220px] max-w-[260px] shadow-lg transition duration-150 relative text-xs select-none backdrop-blur-sm group`}>
      {/* Floating Actions on Selection */}
      {selected && (
        <div className="absolute -top-7 right-1 flex items-center gap-1 z-30">
          <button
            onClick={handlePreview}
            className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-[10px] shadow-md transition"
            title="Preview operator data output"
          >
            <Eye className="h-3 w-3 text-brand-400" />
            <span>Preview</span>
          </button>
          <button
            onClick={handleDelete}
            className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[10px] shadow-md transition"
            title="Delete operator"
          >
            <Trash2 className="h-3 w-3" />
            <span>Delete</span>
          </button>
        </div>
      )}

      {/* Target input handle(s) on Left */}
      {!isSource && !isMultiInput && (
        <Handle
          type="target"
          position={Position.Left}
          id="input"
          className="!w-3 !h-3 !bg-slate-300 !border-2 !border-slate-900 !rounded-full hover:!scale-125 transition"
          title="Input Stream"
        />
      )}

      {/* Multi-stream Target Handles (Join / Lookup) */}
      {isMultiInput && (
        <>
          <Handle
            type="target"
            position={Position.Left}
            id="left"
            style={{ top: '35%' }}
            className="!w-3 !h-3 !bg-pink-400 !border-2 !border-slate-900 !rounded-full hover:!scale-125 transition"
            title="Primary Stream (Left)"
          />
          <Handle
            type="target"
            position={Position.Left}
            id="right"
            style={{ top: '65%' }}
            className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-slate-900 !rounded-full hover:!scale-125 transition"
            title="Secondary Stream (Right)"
          />
        </>
      )}

      {/* Operator Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-slate-800 border border-slate-700/70 shrink-0">
            {getIcon()}
          </div>
          <div>
            <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider font-semibold">
              {opType}
            </div>
            <div className="font-semibold text-slate-200 truncate max-w-[130px]">
              {nodeData.label}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={handlePreview}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-400 transition"
            title="Preview Output"
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={handleDelete}
            className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition"
            title="Delete"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Operator Details Preview */}
      <div className="py-2 space-y-1 text-[11px] font-mono text-slate-400">
        {opType === 'Source' && nodeData.config?.table_name && (
          <div className="truncate text-emerald-400 text-[10px]">
            Table: {nodeData.config.table_name}
          </div>
        )}

        {opType === 'Sink' && nodeData.config?.table_name && (
          <div className="truncate text-rose-400 text-[10px]">
            Write: {nodeData.config.table_name} ({nodeData.config.write_mode || 'append'})
          </div>
        )}

        {opType === 'Filter' && nodeData.config?.column && (
          <div className="truncate text-amber-400 text-[10px]">
            {nodeData.config.column} {nodeData.config.operator || '=='} {String(nodeData.config.value)}
          </div>
        )}

        {opType === 'Join' && nodeData.config?.left_on && (
          <div className="truncate text-pink-400 text-[10px]">
            {nodeData.config.join_type || 'inner'} ON {nodeData.config.left_on}
          </div>
        )}

        {opType === 'Aggregate' && nodeData.config?.group_by && (
          <div className="truncate text-orange-400 text-[10px]">
            Group: {Array.isArray(nodeData.config.group_by) ? nodeData.config.group_by.join(', ') : nodeData.config.group_by}
          </div>
        )}

        {opType === 'Sort' && nodeData.config?.columns && (
          <div className="truncate text-cyan-400 text-[10px]">
            Order: {Array.isArray(nodeData.config.columns) ? nodeData.config.columns.join(', ') : nodeData.config.columns}
          </div>
        )}

        {opType === 'SurrogateKey' && (
          <div className="truncate text-yellow-400 text-[10px]">
            Key: {nodeData.config?.key_name || 'surrogate_key'}
          </div>
        )}
      </div>

      {/* Outgoing Stream Handle on Right */}
      {!isSink && (
        <Handle
          type="source"
          position={Position.Right}
          id="output"
          className="!w-3 !h-3 !bg-brand-500 !border-2 !border-slate-900 !rounded-full hover:!scale-125 transition"
          title="Output Stream"
        />
      )}
    </div>
  );
};
