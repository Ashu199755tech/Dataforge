import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { 
  Database, 
  Layers, 
  Workflow, 
  GitBranch, 
  FileCode, 
  Cloud, 
  Table2, 
  HardDrive,
  ChevronRight
} from 'lucide-react';

export interface LineageNodeData {
  id: string;
  name: string;
  qualified_name: string;
  node_type: string;
  provider: string;
  location_uri?: string;
  schema_columns?: { name: string; type: string }[];
  isSelected?: boolean;
  onSelectColumn?: (nodeId: string, colName: string) => void;
}

export const LineageNodeComponent: React.FC<NodeProps> = memo(({ data, selected }) => {
  const nodeData = data as unknown as LineageNodeData;

  const getNodeIcon = () => {
    switch (nodeData.node_type) {
      case 'Dataset':
        return <Layers className="h-4 w-4 text-brand-400" />;
      case 'Table':
        return <Table2 className="h-4 w-4 text-emerald-400" />;
      case 'StorageFile':
        return <Cloud className="h-4 w-4 text-cyan-400" />;
      case 'Pipeline':
        return <GitBranch className="h-4 w-4 text-purple-400" />;
      case 'DataFlow':
        return <Workflow className="h-4 w-4 text-amber-400" />;
      default:
        return <Database className="h-4 w-4 text-slate-400" />;
    }
  };

  const getProviderBadge = () => {
    const prov = (nodeData.provider || 'generic').toLowerCase();
    let color = 'bg-slate-800 text-slate-300 border-slate-700';
    if (prov.includes('postgres') || prov.includes('mysql')) {
      color = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    } else if (prov.includes('azure') || prov.includes('adls')) {
      color = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
    } else if (prov.includes('s3') || prov.includes('aws')) {
      color = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    } else if (prov.includes('gcs') || prov.includes('gcp')) {
      color = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    } else if (prov.includes('polars')) {
      color = 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    }
    return (
      <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded border ${color}`}>
        {nodeData.provider}
      </span>
    );
  };

  const columns = nodeData.schema_columns || [];

  return (
    <div
      className={`min-w-[220px] max-w-[280px] bg-slate-900 rounded-xl border shadow-xl transition-all ${
        selected
          ? 'border-brand-500 shadow-brand-500/30 ring-2 ring-brand-500/20'
          : 'border-slate-800 hover:border-slate-700'
      }`}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-slate-400 !w-2.5 !h-2.5 !border-2 !border-slate-900"
      />

      {/* Node Header */}
      <div className="p-3 border-b border-slate-800/80 bg-slate-950/60 rounded-t-xl flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="p-1.5 rounded-lg bg-slate-800 border border-slate-700/60 shrink-0">
            {getNodeIcon()}
          </div>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-white truncate" title={nodeData.name}>
              {nodeData.name}
            </div>
            <div className="text-[10px] text-slate-400 font-mono truncate" title={nodeData.qualified_name}>
              {nodeData.node_type}
            </div>
          </div>
        </div>
        {getProviderBadge()}
      </div>

      {/* Node Body / Column Preview */}
      <div className="p-2 space-y-1 text-[11px] max-h-36 overflow-y-auto">
        {columns.length > 0 ? (
          columns.slice(0, 6).map((col, idx) => (
            <div
              key={idx}
              onClick={(e) => {
                e.stopPropagation();
                if (nodeData.onSelectColumn) {
                  nodeData.onSelectColumn(nodeData.id, col.name);
                }
              }}
              className="flex items-center justify-between px-2 py-1 rounded hover:bg-slate-800/70 text-slate-300 hover:text-white cursor-pointer transition group"
              title="Click to trace column lineage"
            >
              <span className="font-mono truncate">{col.name}</span>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-slate-500 font-mono uppercase">{col.type}</span>
                <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-brand-400 transition" />
              </div>
            </div>
          ))
        ) : (
          <div className="px-2 py-1 text-[10px] text-slate-500 italic truncate" title={nodeData.location_uri}>
            {nodeData.location_uri || 'No explicit columns'}
          </div>
        )}
        {columns.length > 6 && (
          <div className="text-[10px] text-brand-400 font-medium px-2 pt-0.5 text-center">
            +{columns.length - 6} more columns
          </div>
        )}
      </div>

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-brand-500 !w-2.5 !h-2.5 !border-2 !border-slate-900"
      />
    </div>
  );
});
LineageNodeComponent.displayName = 'LineageNodeComponent';
