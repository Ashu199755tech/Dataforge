import React, { useState, useEffect } from 'react';
import { 
  X, 
  AlertTriangle, 
  ShieldAlert, 
  CheckCircle2, 
  RefreshCw, 
  Database, 
  Layers, 
  GitBranch, 
  ArrowRight,
  Flame,
  ShieldCheck
} from 'lucide-react';
import api from '../../api/client';

interface LineageNodeOption {
  id: string;
  name: string;
  node_type: string;
  provider: string;
  schema_columns?: { name: string; type: string }[];
}

interface ImpactAnalysisResponse {
  target_node_id: string;
  target_node_name: string;
  target_column?: string;
  risk_level: 'High' | 'Medium' | 'Low';
  summary_message: string;
  affected_pipelines_count: number;
  affected_datasets_count: number;
  affected_columns_count: number;
  affected_nodes: { id: string; name: string; node_type: string; provider: string }[];
}

interface ImpactAnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  nodes: LineageNodeOption[];
  initialNodeId?: string | null;
  initialColumn?: string | null;
}

export const ImpactAnalysisModal: React.FC<ImpactAnalysisModalProps> = ({
  isOpen,
  onClose,
  projectId,
  nodes,
  initialNodeId,
  initialColumn
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string>(initialNodeId || (nodes[0]?.id || ''));
  const [selectedColumn, setSelectedColumn] = useState<string>(initialColumn || '');
  const [impactReport, setImpactReport] = useState<ImpactAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialNodeId) {
      setSelectedNodeId(initialNodeId);
    } else if (nodes.length > 0 && !selectedNodeId) {
      setSelectedNodeId(nodes[0].id);
    }
    if (initialColumn) {
      setSelectedColumn(initialColumn);
    }
  }, [initialNodeId, initialColumn, nodes]);

  const selectedNode = nodes.find(n => n.id === selectedNodeId);
  const availableColumns = selectedNode?.schema_columns || [];

  const handleRunAnalysis = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!selectedNodeId) return;

    try {
      setIsLoading(true);
      setError(null);
      const res = await api.post<ImpactAnalysisResponse>(`/lineage/impact-analysis?project_id=${projectId}`, {
        node_id: selectedNodeId,
        column_name: selectedColumn.trim() || undefined
      });
      setImpactReport(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to execute impact analysis');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
              <Flame className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Downstream Impact & Blast Radius Analysis</h2>
              <p className="text-xs text-slate-400">
                Determine what breaks downstream before deleting or modifying schema definitions
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form and Controls */}
        <div className="p-6 space-y-4 flex-1 overflow-y-auto text-xs">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-slate-300 font-medium">Select Target Asset</label>
              <select
                value={selectedNodeId}
                onChange={(e) => {
                  setSelectedNodeId(e.target.value);
                  setSelectedColumn('');
                }}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-brand-500"
              >
                {nodes.map(n => (
                  <option key={n.id} value={n.id}>
                    [{n.node_type}] {n.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-slate-300 font-medium">Specific Column (Optional)</label>
              <select
                value={selectedColumn}
                onChange={(e) => setSelectedColumn(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-brand-500"
              >
                <option value="">-- All Columns (Table/Dataset Level) --</option>
                {availableColumns.map(c => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.type})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={() => handleRunAnalysis()}
            disabled={isLoading || !selectedNodeId}
            className="w-full py-2 bg-brand-600 hover:bg-brand-500 text-white font-semibold rounded-lg shadow-lg shadow-brand-600/30 flex items-center justify-center gap-2 transition"
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Simulating Downstream Dependency Traversal...
              </>
            ) : (
              <>
                <Flame className="h-4 w-4" />
                Analyze Downstream Impact
              </>
            )}
          </button>

          {/* Analysis Report Section */}
          {impactReport && (
            <div className="pt-3 border-t border-slate-800 space-y-4">
              {/* Severity Banner */}
              <div className={`p-4 rounded-xl border flex items-start gap-3 ${
                impactReport.risk_level === 'High'
                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  : impactReport.risk_level === 'Medium'
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                  : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              }`}>
                {impactReport.risk_level === 'High' ? (
                  <ShieldAlert className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
                ) : impactReport.risk_level === 'Medium' ? (
                  <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
                ) : (
                  <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="font-bold text-sm text-white flex items-center gap-2">
                    Risk Assessment: {impactReport.risk_level} Severity
                  </div>
                  <p className="text-xs leading-relaxed mt-1 opacity-90">
                    {impactReport.summary_message}
                  </p>
                </div>
              </div>

              {/* Metric Counters */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Affected Pipelines</div>
                  <div className="text-xl font-bold text-white mt-1">{impactReport.affected_pipelines_count}</div>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Affected Datasets</div>
                  <div className="text-xl font-bold text-brand-400 mt-1">{impactReport.affected_datasets_count}</div>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
                  <div className="text-slate-400 text-[10px] uppercase font-semibold">Affected Columns</div>
                  <div className="text-xl font-bold text-cyan-400 mt-1">{impactReport.affected_columns_count}</div>
                </div>
              </div>

              {/* Affected Assets List */}
              {impactReport.affected_nodes.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    Downstream Dependent Entities ({impactReport.affected_nodes.length})
                  </div>
                  <div className="max-h-44 overflow-y-auto space-y-1.5 pr-1">
                    {impactReport.affected_nodes.map(n => (
                      <div
                        key={n.id}
                        className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Database className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                          <div className="truncate">
                            <span className="text-white font-medium">{n.name}</span>
                            <span className="text-slate-500 text-[10px] ml-2 font-mono">({n.node_type})</span>
                          </div>
                        </div>
                        <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                          {n.provider}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs text-slate-400 hover:text-white rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
