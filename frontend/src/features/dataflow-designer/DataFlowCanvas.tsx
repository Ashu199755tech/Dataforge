import React, { useState, useCallback, useRef, useEffect } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  applyNodeChanges, 
  applyEdgeChanges, 
  addEdge, 
  Node, 
  Edge, 
  Connection as FlowConnection,
  ReactFlowInstance,
  Panel
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { DataFlowNode } from './DataFlowNode';
import { DataFlowToolbox } from './DataFlowToolbox';
import { DataFlowConfigDrawer } from './DataFlowConfigDrawer';
import api from '../../api/client';
import { 
  Save, 
  Play, 
  ArrowLeft, 
  CheckCircle2, 
  AlertCircle, 
  Loader2 
} from 'lucide-react';

const nodeTypes = {
  dataFlowNode: DataFlowNode,
};

interface DataFlowCanvasProps {
  dataflowId: string;
  onBack: () => void;
}

export const DataFlowCanvas: React.FC<DataFlowCanvasProps> = ({ dataflowId, onBack }) => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [dataflowName, setDataflowName] = useState<string>('Loading Data Flow...');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [runMetrics, setRunMetrics] = useState<any>(null);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  // Load Data Flow details
  useEffect(() => {
    const loadDataFlow = async () => {
      try {
        const res = await api.get(`/dataflows/${dataflowId}`);
        setDataflowName(res.data.name);
        const graph = res.data.graph_json || {};
        
        // Attach callbacks to nodes
        const loadedNodes = (graph.nodes || []).map((n: Node) => ({
          ...n,
          type: 'dataFlowNode',
          data: {
            ...n.data,
            onDelete: (id: string) => handleDeleteNode(id),
            onPreview: (id: string) => {
              const target = (graph.nodes || []).find((node: Node) => node.id === id);
              if (target) setSelectedNode(target);
            }
          }
        }));
        setNodes(loadedNodes);
        setEdges(graph.edges || []);
      } catch (err) {
        console.error('Failed to load Data Flow:', err);
      }
    };
    loadDataFlow();
  }, [dataflowId]);

  const onNodesChange = useCallback(
    (changes: any) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes: any) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onConnect = useCallback(
    (params: FlowConnection) => {
      setEdges((eds) => addEdge({
        ...params,
        animated: true,
        style: { stroke: '#06b6d4', strokeWidth: 2 }
      }, eds));
    },
    []
  );

  const onNodeClick = (_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  };

  const onPaneClick = () => {
    setSelectedNode(null);
  };

  const handleDeleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNode?.id === nodeId) {
      setSelectedNode(null);
    }
  };

  const handleUpdateNode = (nodeId: string, updatedData: any) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: updatedData } : n))
    );
    if (selectedNode?.id === nodeId) {
      setSelectedNode((prev) => (prev ? { ...prev, data: updatedData } : null));
    }
  };

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const rawData = event.dataTransfer.getData('application/dataflow-operator');
      if (!rawData || !reactFlowInstance || !reactFlowWrapper.current) return;

      const { nodeType, label } = JSON.parse(rawData);
      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNodeId = `${nodeType.toLowerCase()}_${Date.now()}`;
      const newNode: Node = {
        id: newNodeId,
        type: 'dataFlowNode',
        position,
        data: {
          label: `${label} 1`,
          operatorType: nodeType,
          config: {},
          onDelete: (id: string) => handleDeleteNode(id),
          onPreview: (id: string) => {
            setSelectedNode(newNode);
          }
        },
      };

      setNodes((nds) => nds.concat(newNode));
      setSelectedNode(newNode);
    },
    [reactFlowInstance]
  );

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const graph_json = {
        nodes: nodes.map(({ id, position, data }) => ({
          id,
          type: 'dataFlowNode',
          position,
          data: {
            label: data.label,
            operatorType: data.operatorType,
            config: data.config
          }
        })),
        edges: edges.map(({ id, source, target, sourceHandle, targetHandle }) => ({
          id,
          source,
          target,
          sourceHandle,
          targetHandle
        }))
      };

      await api.put(`/dataflows/${dataflowId}`, { graph_json });
      setSaveStatus('Saved successfully');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err: any) {
      setSaveStatus('Save failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsSaving(false);
    }
  };

  const handleExecute = async () => {
    setIsRunning(true);
    setRunMetrics(null);
    try {
      await handleSave();
      const res = await api.post(`/dataflows/${dataflowId}/execute`);
      setRunMetrics(res.data);
    } catch (err: any) {
      alert('Execution failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 overflow-hidden">
      {/* Top Navigation Bar */}
      <div className="h-12 border-b border-slate-800 bg-slate-900/90 px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Data Flows</span>
          </button>
          <div className="h-4 w-px bg-slate-800" />
          <h2 className="text-xs font-bold text-slate-200">
            {dataflowName}
          </h2>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-brand-500/10 text-brand-400 border border-brand-500/20">
            Polars Vectorized
          </span>
        </div>

        <div className="flex items-center gap-2">
          {saveStatus && (
            <span className="text-[11px] text-emerald-400 flex items-center gap-1 font-medium">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{saveStatus}</span>
            </span>
          )}

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition"
          >
            <Save className="h-3.5 w-3.5" />
            <span>{isSaving ? 'Saving...' : 'Save Graph'}</span>
          </button>

          <button
            onClick={handleExecute}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md shadow-brand-500/20 transition disabled:opacity-50"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Transforming...</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span>Run Data Flow</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Designer Area */}
      <div className="flex-1 flex overflow-hidden relative">
        <DataFlowToolbox />

        <div className="flex-1 h-full relative" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onInit={setReactFlowInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            fitView
            className="bg-slate-950"
          >
            <Background color="#1e293b" gap={20} size={1} />
            <Controls className="!bg-slate-900 !border-slate-800 !text-slate-300" />

            {runMetrics && (
              <Panel position="bottom-left" className="m-3">
                <div className="p-3 rounded-lg bg-slate-900/95 border border-emerald-500/40 text-xs text-slate-200 shadow-xl space-y-1">
                  <div className="font-semibold text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Data Flow Executed Successfully!</span>
                  </div>
                  <div className="text-[11px] font-mono text-slate-400">
                    Read: <strong className="text-slate-200">{runMetrics.total_rows_read}</strong> rows | Written: <strong className="text-slate-200">{runMetrics.total_rows_written}</strong> rows | Duration: <strong className="text-slate-200">{runMetrics.duration_seconds}s</strong>
                  </div>
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>

        {selectedNode && (
          <DataFlowConfigDrawer
            selectedNode={selectedNode}
            dataflowId={dataflowId}
            onUpdateNode={handleUpdateNode}
            onDeleteNode={handleDeleteNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
};
