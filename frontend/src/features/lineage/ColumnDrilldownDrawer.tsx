import React, { useState, useEffect } from 'react';
import { 
  X, 
  ArrowRight, 
  Layers, 
  GitBranch, 
  Code2, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  Compass, 
  Database,
  ArrowUpLeft,
  ArrowDownRight
} from 'lucide-react';
import api from '../../api/client';

interface ColumnTraceStep {
  edge_id: string;
  source_node_id: string;
  source_node_name: string;
  source_column: string;
  target_node_id: string;
  target_node_name: string;
  target_column: string;
  transformation_type: string;
  expression?: string;
  confidence: string;
}

interface ColumnTraceResponse {
  column_name: string;
  node_id: string;
  node_name: string;
  direction: string;
  trace_steps: ColumnTraceStep[];
}

interface ColumnDrilldownDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  nodeId: string | null;
  nodeName: string | null;
  columnName: string | null;
}

export const ColumnDrilldownDrawer: React.FC<ColumnDrilldownDrawerProps> = ({
  isOpen,
  onClose,
  projectId,
  nodeId,
  nodeName,
  columnName
}) => {
  const [direction, setDirection] = useState<'upstream' | 'downstream'>('upstream');
  const [traceData, setTraceData] = useState<ColumnTraceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && nodeId && columnName) {
      loadTrace(direction);
    }
  }, [isOpen, nodeId, columnName, direction]);

  const loadTrace = async (dir: 'upstream' | 'downstream') => {
    if (!nodeId || !columnName) return;
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.get<ColumnTraceResponse>(
        `/lineage/column-trace?project_id=${projectId}&node_id=${nodeId}&column=${encodeURIComponent(columnName)}&direction=${dir}`
      );
      setTraceData(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to trace column lineage');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const getConfidenceBadge = (confidence: string) => {
    switch (confidence.toLowerCase()) {
      case 'exact':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Exact Match
          </span>
        );
      case 'derived':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Derived / Computed
          </span>
        );
      case 'partial':
      default:
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Partial / Wildcard
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col font-sans">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/80 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-brand-500/20 text-brand-400 border border-brand-500/30">
            <Compass className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Column Lineage Drilldown</h3>
            <p className="text-[11px] text-slate-400 font-mono">
              {nodeName} &rarr; <span className="text-brand-300 font-bold">{columnName}</span>
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Direction Toggle */}
      <div className="p-3 bg-slate-950/40 border-b border-slate-800/80 flex items-center gap-2">
        <button
          onClick={() => setDirection('upstream')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
            direction === 'upstream'
              ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <ArrowUpLeft className="h-3.5 w-3.5" />
          Upstream Origins
        </button>
        <button
          onClick={() => setDirection('downstream')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
            direction === 'downstream'
              ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <ArrowDownRight className="h-3.5 w-3.5" />
          Downstream Targets
        </button>
      </div>

      {/* Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {isLoading ? (
          <div className="py-12 text-center text-slate-500">
            <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-brand-400" />
            Tracing column transformation tree...
          </div>
        ) : error ? (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : traceData && traceData.trace_steps.length > 0 ? (
          <div className="space-y-3">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              {direction === 'upstream' ? 'Origin Dependency Path' : 'Consumption Destinations'} ({traceData.trace_steps.length} hops)
            </div>

            <div className="space-y-3 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-[2px] before:bg-slate-800">
              {traceData.trace_steps.map((step, idx) => (
                <div key={idx} className="relative pl-7 group">
                  <div className="absolute left-1.5 top-3 -translate-y-1/2 h-3.5 w-3.5 rounded-full bg-slate-900 border-2 border-brand-500 flex items-center justify-center">
                    <div className="h-1.5 w-1.5 rounded-full bg-brand-400" />
                  </div>

                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-white font-semibold truncate flex items-center gap-1.5">
                        <Database className="h-3.5 w-3.5 text-brand-400 shrink-0" />
                        <span className="truncate">{step.source_node_name}</span>
                      </div>
                      {getConfidenceBadge(step.confidence)}
                    </div>

                    <div className="flex items-center gap-2 text-[11px] font-mono bg-slate-900 p-2 rounded border border-slate-800/80">
                      <span className="text-cyan-400 font-bold">{step.source_column}</span>
                      <ArrowRight className="h-3 w-3 text-slate-500 shrink-0" />
                      <span className="text-emerald-400 font-bold">{step.target_column}</span>
                    </div>

                    {step.expression && (
                      <div className="text-[10px] text-slate-400 font-mono bg-slate-900/60 p-2 rounded border border-slate-800/60">
                        <span className="text-slate-500 select-none">Formula: </span>
                        <code className="text-brand-300">{step.expression}</code>
                      </div>
                    )}

                    <div className="text-[10px] text-slate-500 flex items-center justify-between pt-1">
                      <span>Type: <span className="text-slate-300 capitalize">{step.transformation_type}</span></span>
                      <span className="truncate">Target: {step.target_node_name}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-12 text-center text-slate-500">
            <CheckCircle2 className="h-6 w-6 text-emerald-400 mx-auto mb-2" />
            No {direction} dependencies found. This column is an origin root.
          </div>
        )}
      </div>
    </div>
  );
};
