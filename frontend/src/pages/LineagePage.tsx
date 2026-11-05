import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  MiniMap, 
  Node, 
  Edge, 
  useNodesState, 
  useEdgesState,
  MarkerType
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  Network, 
  RefreshCw, 
  Search, 
  Filter, 
  Flame, 
  Download, 
  Layers, 
  Table2, 
  Cloud, 
  GitBranch, 
  Workflow, 
  Compass, 
  CheckCircle2, 
  AlertTriangle,
  RotateCcw
} from 'lucide-react';
import api from '../api/client';
import { useAppStore } from '../store/useAppStore';
import { LineageNodeComponent, LineageNodeData } from '../features/lineage/LineageNodeComponent';
import { ColumnDrilldownDrawer } from '../features/lineage/ColumnDrilldownDrawer';
import { ImpactAnalysisModal } from '../features/lineage/ImpactAnalysisModal';

interface LineageNodeDTO {
  id: string;
  project_id: string;
  node_type: string;
  name: string;
  qualified_name: string;
  provider: string;
  location_uri?: string;
  schema_json?: { name: string; type: string }[];
}

interface LineageEdgeDTO {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  confidence: string;
  activity_name?: string;
}

interface LineageGraphDTO {
  nodes: LineageNodeDTO[];
  edges: LineageEdgeDTO[];
  column_lineage: any[];
}

const nodeTypes = {
  lineageNode: LineageNodeComponent,
};

export const LineagePage: React.FC = () => {
  const { activeProject } = useAppStore();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [rawGraph, setRawGraph] = useState<LineageGraphDTO | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState('ALL');
  const [directionFilter, setDirectionFilter] = useState<'both' | 'upstream' | 'downstream'>('both');
  const [focalNodeId, setFocalNodeId] = useState<string | null>(null);

  // Column Drilldown Drawer state
  const [drilldownNodeId, setDrilldownNodeId] = useState<string | null>(null);
  const [drilldownNodeName, setDrilldownNodeName] = useState<string | null>(null);
  const [drilldownColumn, setDrilldownColumn] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Impact Analysis Modal state
  const [isImpactModalOpen, setIsImpactModalOpen] = useState(false);

  const handleSelectColumn = useCallback((nodeId: string, colName: string) => {
    const n = rawGraph?.nodes.find(item => item.id === nodeId);
    setDrilldownNodeId(nodeId);
    setDrilldownNodeName(n?.name || 'Asset');
    setDrilldownColumn(colName);
    setIsDrawerOpen(true);
  }, [rawGraph?.nodes]);

  const fetchGraph = useCallback(async (rootId?: string | null, dir: string = 'both') => {
    if (!activeProject?.id) return;
    try {
      setIsLoading(true);
      setError(null);

      let url = `/lineage/graph?project_id=${activeProject.id}&direction=${dir}&depth=10`;
      if (rootId) {
        url += `&root_id=${rootId}`;
      }
      const res = await api.get<LineageGraphDTO>(url);
      setRawGraph(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load lineage graph');
    } finally {
      setIsLoading(false);
    }
  }, [activeProject?.id]);

  useEffect(() => {
    fetchGraph(focalNodeId, directionFilter);
  }, [fetchGraph, focalNodeId, directionFilter]);

  // Compute Layout (simple topological tier placement)
  useEffect(() => {
    if (!rawGraph) return;

    // Filter nodes by search query and type
    const filteredRawNodes = rawGraph.nodes.filter(n => {
      const matchesSearch = n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            n.qualified_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = selectedTypeFilter === 'ALL' || n.node_type.toUpperCase() === selectedTypeFilter.toUpperCase();
      return matchesSearch && matchesType;
    });

    const nodeIds = new Set(filteredRawNodes.map(n => n.id));

    // Calculate in-degrees to determine levels
    const inDegree: Record<string, number> = {};
    const adj: Record<string, string[]> = {};
    filteredRawNodes.forEach(n => {
      inDegree[n.id] = 0;
      adj[n.id] = [];
    });

    rawGraph.edges.forEach(e => {
      if (nodeIds.has(e.source_node_id) && nodeIds.has(e.target_node_id)) {
        adj[e.source_node_id].push(e.target_node_id);
        inDegree[e.target_node_id] = (inDegree[e.target_node_id] || 0) + 1;
      }
    });

    // Assign tiers
    const levels: Record<string, number> = {};
    const queue: string[] = [];
    filteredRawNodes.forEach(n => {
      if (inDegree[n.id] === 0) {
        levels[n.id] = 0;
        queue.push(n.id);
      }
    });

    while (queue.length > 0) {
      const u = queue.shift()!;
      const curLevel = levels[u] || 0;
      for (const v of adj[u] || []) {
        inDegree[v]--;
        levels[v] = Math.max(levels[v] || 0, curLevel + 1);
        if (inDegree[v] === 0) {
          queue.push(v);
        }
      }
    }

    // Default any remaining cyclic / unassigned nodes
    filteredRawNodes.forEach(n => {
      if (levels[n.id] === undefined) levels[n.id] = 1;
    });

    // Group nodes by level for grid layout
    const levelGroups: Record<number, LineageNodeDTO[]> = {};
    filteredRawNodes.forEach(n => {
      const lvl = levels[n.id] || 0;
      if (!levelGroups[lvl]) levelGroups[lvl] = [];
      levelGroups[lvl].push(n);
    });

    const flowNodes: Node[] = [];
    const X_SPACING = 360;
    const Y_SPACING = 180;

    Object.keys(levelGroups).forEach(lvlStr => {
      const lvl = parseInt(lvlStr, 10);
      const group = levelGroups[lvl];
      group.forEach((n, idx) => {
        flowNodes.push({
          id: n.id,
          type: 'lineageNode',
          position: {
            x: lvl * X_SPACING + 50,
            y: idx * Y_SPACING + 50
          },
          data: {
            id: n.id,
            name: n.name,
            qualified_name: n.qualified_name,
            node_type: n.node_type,
            provider: n.provider,
            location_uri: n.location_uri,
            schema_columns: n.schema_json || [],
            onSelectColumn: handleSelectColumn
          } as any
        });
      });
    });

    // Build flow edges
    const flowEdges: Edge[] = [];
    rawGraph.edges.forEach(e => {
      if (nodeIds.has(e.source_node_id) && nodeIds.has(e.target_node_id)) {
        let strokeColor = '#10b981'; // exact - green
        let strokeDasharray = undefined;

        if (e.confidence === 'derived') {
          strokeColor = '#3b82f6'; // derived - blue
        } else if (e.confidence === 'partial' || e.confidence === 'unknown') {
          strokeColor = '#f59e0b'; // partial - amber
          strokeDasharray = '5 5';
        }

        flowEdges.push({
          id: e.id,
          source: e.source_node_id,
          target: e.target_node_id,
          type: 'smoothstep',
          animated: e.confidence === 'exact',
          style: {
            stroke: strokeColor,
            strokeWidth: 2,
            strokeDasharray
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: strokeColor,
            width: 16,
            height: 16
          },
          label: e.activity_name || undefined,
          labelStyle: { fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }
        });
      }
    });

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [rawGraph, searchQuery, selectedTypeFilter, handleSelectColumn, setNodes, setEdges]);

  const handleExtractLineage = async () => {
    if (!activeProject?.id) return;
    try {
      setIsExtracting(true);
      await api.post(`/lineage/extract?project_id=${activeProject.id}`);
      await fetchGraph(focalNodeId, directionFilter);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Lineage extraction failed');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExportJson = () => {
    if (!rawGraph) return;
    const blob = new Blob([JSON.stringify(rawGraph, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dataforge-lineage-${activeProject?.name || 'export'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalNodesCount = rawGraph?.nodes.length || 0;
  const totalEdgesCount = rawGraph?.edges.length || 0;
  const totalColsCount = rawGraph?.column_lineage.length || 0;

  return (
    <div className="flex flex-col h-full bg-slate-950 text-white font-sans overflow-hidden">
      {/* Top Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-tr from-brand-600 to-cyan-500 text-white shadow-lg shadow-brand-500/20">
            <Network className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              Data Lineage & Impact Analysis
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-normal border border-slate-700">
                End-to-End Governance
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Interactive source-to-sink graph with column-level precision and downstream impact simulation
            </p>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsImpactModalOpen(true)}
            className="px-3.5 py-2 text-xs font-semibold text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-lg transition flex items-center gap-1.5 shadow-lg shadow-rose-500/10"
          >
            <Flame className="h-4 w-4 text-rose-400" />
            Impact Analysis
          </button>

          <button
            onClick={handleExportJson}
            className="px-3.5 py-2 text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition flex items-center gap-1.5"
          >
            <Download className="h-4 w-4 text-brand-400" />
            Export Graph
          </button>

          <button
            onClick={handleExtractLineage}
            disabled={isExtracting}
            className="px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-2 transition"
          >
            <RefreshCw className={`h-4 w-4 ${isExtracting ? 'animate-spin' : ''}`} />
            {isExtracting ? 'Extracting...' : 'Scan & Extract Lineage'}
          </button>
        </div>
      </div>

      {/* Filter and Control Bar */}
      <div className="px-4 py-2.5 border-b border-slate-800 bg-slate-900/40 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
        <div className="flex items-center gap-2">
          {/* Search Input */}
          <div className="relative w-64">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search assets or tables..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Type Filter Pills */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {['ALL', 'Dataset', 'Table', 'StorageFile', 'DataFlow'].map(type => (
              <button
                key={type}
                onClick={() => setSelectedTypeFilter(type)}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition ${
                  selectedTypeFilter === type
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {type === 'ALL' ? 'All Entities' : type}
              </button>
            ))}
          </div>
        </div>

        {/* Direction Toggle & Reset */}
        <div className="flex items-center gap-3">
          {focalNodeId && (
            <div className="flex items-center gap-2 bg-slate-950 px-2 py-1 rounded border border-brand-500/30 text-[11px]">
              <span className="text-slate-400">Focused View:</span>
              <span className="text-brand-300 font-semibold">{rawGraph?.nodes.find(n => n.id === focalNodeId)?.name}</span>
              <button
                onClick={() => setFocalNodeId(null)}
                className="text-slate-500 hover:text-white ml-1"
                title="Reset to Full Graph"
              >
                <RotateCcw className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Statistics Display */}
          <div className="flex items-center gap-3 text-[11px] text-slate-400 border-l border-slate-800 pl-3">
            <span>Nodes: <strong className="text-white">{totalNodesCount}</strong></span>
            <span>Flows: <strong className="text-brand-400">{totalEdgesCount}</strong></span>
            <span>Column Links: <strong className="text-emerald-400">{totalColsCount}</strong></span>
          </div>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 relative overflow-hidden bg-slate-950">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/60 z-20">
            <div className="text-center">
              <RefreshCw className="h-8 w-8 animate-spin text-brand-400 mx-auto mb-2" />
              <p className="text-xs text-slate-400">Loading enterprise lineage graph...</p>
            </div>
          </div>
        ) : nodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 z-10 p-6 text-center">
            <Network className="h-12 w-12 text-slate-600 mb-3" />
            <h3 className="text-base font-semibold text-slate-300">No Lineage Relationships Discovered Yet</h3>
            <p className="text-xs text-slate-500 max-w-md mt-1 mb-4">
              Click "Scan & Extract Lineage" to automatically trace data movement across your pipelines, Copy Data activities, and DataFlow transformations.
            </p>
            <button
              onClick={handleExtractLineage}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Scan & Extract Lineage
            </button>
          </div>
        ) : null}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => {
            setFocalNodeId(node.id);
          }}
          fitView
          className="bg-slate-950"
        >
          <Background color="#1e293b" gap={20} size={1} />
          <Controls className="!bg-slate-900 !border !border-slate-800 !text-white fill-white" />
          <MiniMap 
            nodeColor="#334155" 
            maskColor="rgba(2, 6, 23, 0.7)" 
            className="!bg-slate-900 !border !border-slate-800 rounded-lg overflow-hidden" 
          />
        </ReactFlow>
      </div>

      {/* Column Drilldown Drawer */}
      {activeProject && (
        <ColumnDrilldownDrawer
          isOpen={isDrawerOpen}
          onClose={() => setIsDrawerOpen(false)}
          projectId={activeProject.id}
          nodeId={drilldownNodeId}
          nodeName={drilldownNodeName}
          columnName={drilldownColumn}
        />
      )}

      {/* Impact Analysis Modal */}
      {activeProject && (
        <ImpactAnalysisModal
          isOpen={isImpactModalOpen}
          onClose={() => setIsImpactModalOpen(false)}
          projectId={activeProject.id}
          nodes={rawGraph?.nodes.map(n => ({
            id: n.id,
            name: n.name,
            node_type: n.node_type,
            provider: n.provider,
            schema_columns: n.schema_json || []
          })) || []}
          initialNodeId={focalNodeId}
        />
      )}
    </div>
  );
};
