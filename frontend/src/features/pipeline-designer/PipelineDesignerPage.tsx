import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  BackgroundVariant
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAppStore } from '../../store/useAppStore';
import { ActivityToolbox } from './ActivityToolbox';
import { ActivityNode } from './ActivityNode';
import { ActivityConfigDrawer } from './ActivityConfigDrawer';
import api from '../../api/client';
import { 
  Save, 
  Play, 
  CheckCircle, 
  ArrowLeft, 
  AlertTriangle,
  RotateCcw
} from 'lucide-react';

export const PipelineDesignerPage: React.FC = () => {
  const { selectedPipelineId, pipelines, fetchPipelines, setCurrentTab } = useAppStore();
  const [pipeline, setPipeline] = useState<any>(null);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [validationMsg, setValidationMsg] = useState<{ valid: boolean; text: string } | null>(null);

  const nodeTypes = useMemo(() => ({ activityNode: ActivityNode }), []);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Load pipeline data
  useEffect(() => {
    if (!selectedPipelineId) return;
    const loadPipe = async () => {
      try {
        const res = await api.get(`/pipelines/${selectedPipelineId}`);
        setPipeline(res.data);
        const def = res.data.definition_json || {};

        if (def.nodes && def.nodes.length > 0) {
          setNodes(def.nodes);
          setEdges(def.edges || []);
        } else if (def.activities && def.activities.length > 0) {
          // Convert activities to nodes
          const generatedNodes: Node[] = def.activities.map((act: any, idx: number) => ({
            id: act.id,
            type: 'activityNode',
            position: { x: 150 + idx * 260, y: 150 },
            data: {
              label: act.name,
              activityType: act.type,
              config: act.config || {}
            }
          }));

          const generatedEdges: Edge[] = [];
          def.activities.forEach((act: any) => {
            (act.depends_on || []).forEach((dep: any) => {
              const parentId = typeof dep === 'string' ? dep : dep.activity_id;
              generatedEdges.push({
                id: `e-${parentId}-${act.id}`,
                source: parentId,
                target: act.id,
                animated: true
              });
            });
          });

          setNodes(generatedNodes);
          setEdges(generatedEdges);
        } else {
          // Default initial empty canvas
          setNodes([]);
          setEdges([]);
        }
      } catch (err) {
        console.error('Failed to load pipeline', err);
      }
    };
    loadPipe();
  }, [selectedPipelineId]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true }, eds)),
    [setEdges]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow-type');
      const label = event.dataTransfer.getData('application/reactflow-label');

      if (!type) return;

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - reactFlowBounds.left - 100,
        y: event.clientY - reactFlowBounds.top - 40,
      };

      const newId = `act_${Date.now()}`;
      const newNode: Node = {
        id: newId,
        type: 'activityNode',
        position,
        data: {
          label: label || 'New Activity',
          activityType: type,
          config: {
            source: {},
            destination: {},
            rules: []
          }
        },
      };

      setNodes((nds) => nds.concat(newNode));
      setSelectedNode(newNode);
    },
    [setNodes]
  );

  const handleNodeClick = (_: any, node: Node) => {
    setSelectedNode(node);
  };

  const handleUpdateNode = (nodeId: string, updatedData: any) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          const updated = { ...n, data: updatedData };
          setSelectedNode(updated);
          return updated;
        }
        return n;
      })
    );
  };

  const constructPipelineDefinition = () => {
    // Convert nodes & edges to executable activity JSON
    const activities = nodes.map((n) => {
      const incomingEdges = edges.filter((e) => e.target === n.id);
      const depends_on = incomingEdges.map((e) => ({
        activity_id: e.source,
        condition: 'Succeeded'
      }));

      return {
        id: n.id,
        name: n.data.label,
        type: n.data.activityType,
        depends_on,
        config: n.data.config || {}
      };
    });

    return {
      parameters: pipeline?.definition_json?.parameters || {},
      variables: pipeline?.definition_json?.variables || { high_watermark: '1970-01-01 00:00:00' },
      activities,
      nodes,
      edges
    };
  };

  const handleValidateDAG = async () => {
    if (!selectedPipelineId) return;
    const def = constructPipelineDefinition();
    try {
      await api.put(`/pipelines/${selectedPipelineId}`, { definition_json: def });
      const res = await api.post(`/pipelines/${selectedPipelineId}/validate`);
      setValidationMsg({ valid: res.data.valid, text: res.data.message });
    } catch (err: any) {
      setValidationMsg({ valid: false, text: err.response?.data?.detail || err.message });
    }
  };

  const handleSavePipeline = async () => {
    if (!selectedPipelineId) return;
    setIsSaving(true);
    try {
      const def = constructPipelineDefinition();
      const res = await api.put(`/pipelines/${selectedPipelineId}`, {
        definition_json: def,
        status: 'Published'
      });
      setPipeline(res.data);
      await fetchPipelines();
      setValidationMsg({ valid: true, text: 'Pipeline successfully published and saved!' });
    } catch (err: any) {
      alert(`Error saving pipeline: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRunPipeline = async () => {
    if (!selectedPipelineId) return;
    setIsRunning(true);
    try {
      // First save latest layout
      const def = constructPipelineDefinition();
      await api.put(`/pipelines/${selectedPipelineId}`, { definition_json: def });
      // Then trigger run
      await api.post(`/pipelines/${selectedPipelineId}/run`);
      setCurrentTab('runs');
    } catch (err: any) {
      alert(`Error executing pipeline: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col overflow-hidden">
      {/* Top Designer Sub-Header */}
      <div className="h-12 border-b border-slate-800 bg-slate-900/95 px-4 flex items-center justify-between z-10 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setCurrentTab('pipelines')}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
            title="Back to Pipelines"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-white">
                {pipeline?.name || 'Loading pipeline...'}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20 font-mono">
                v{pipeline?.current_version || 1}
              </span>
            </div>
          </div>
        </div>

        {/* Validation Alert Pill */}
        {validationMsg && (
          <div className={`hidden md:flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border ${
            validationMsg.valid 
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' 
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}>
            {validationMsg.valid ? <CheckCircle className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
            <span className="truncate max-w-sm">{validationMsg.text}</span>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={handleValidateDAG}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition font-medium border border-slate-700/60"
          >
            <CheckCircle className="h-3.5 w-3.5 text-brand-400" />
            <span>Validate DAG</span>
          </button>

          <button
            onClick={handleSavePipeline}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition font-medium border border-slate-700/60 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5 text-emerald-400" />
            <span>{isSaving ? 'Saving...' : 'Save & Publish'}</span>
          </button>

          <button
            onClick={handleRunPipeline}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition font-semibold shadow-sm disabled:opacity-50"
          >
            <Play className={`h-3.5 w-3.5 ${isRunning ? 'animate-spin' : ''}`} />
            <span>{isRunning ? 'Running...' : 'Run Pipeline'}</span>
          </button>
        </div>
      </div>

      {/* Main Designer Canvas Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Activity Toolbox */}
        <ActivityToolbox />

        {/* Central Infinite React Flow Canvas */}
        <div className="flex-1 h-full bg-slate-950 relative" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={handleNodeClick}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background color="#1e293b" gap={20} size={1.5} variant={BackgroundVariant.Dots} />
            <Controls className="!bg-slate-900 !border-slate-800 !text-white !fill-white" />
            <MiniMap 
              className="!bg-slate-900 !border-slate-800"
              nodeColor={() => '#38a8f6'}
              maskColor="rgba(10, 15, 29, 0.7)"
            />
          </ReactFlow>
        </div>

        {/* Right Configuration Drawer */}
        {selectedNode && (
          <ActivityConfigDrawer
            selectedNode={selectedNode}
            onUpdateNode={handleUpdateNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
};
