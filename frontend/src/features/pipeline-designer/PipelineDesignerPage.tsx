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
  RotateCcw,
  Trash2
} from 'lucide-react';

export const getConditionEdgeProperties = (condOrHandle: string) => {
  const norm = (condOrHandle || '').toLowerCase();
  if (norm === 'failure' || norm === 'failed') {
    return {
      condition: 'Failed',
      color: '#ef4444',
      label: 'On Failure',
      sourceHandle: 'failure'
    };
  } else if (norm === 'completion' || norm === 'completed') {
    return {
      condition: 'Completed',
      color: '#3b82f6',
      label: 'On Completion',
      sourceHandle: 'completion'
    };
  } else if (norm === 'skipped' || norm === 'skip') {
    return {
      condition: 'Skipped',
      color: '#94a3b8',
      label: 'On Skip',
      sourceHandle: 'skipped'
    };
  } else {
    return {
      condition: 'Succeeded',
      color: '#10b981',
      label: 'On Success',
      sourceHandle: 'success'
    };
  }
};

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

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      setSelectedNode((curr: any) => (curr?.id === nodeId ? null : curr));
    },
    [setNodes, setEdges]
  );

  // Load pipeline data
  useEffect(() => {
    if (!selectedPipelineId) return;
    const loadPipe = async () => {
      try {
        const res = await api.get(`/pipelines/${selectedPipelineId}`);
        setPipeline(res.data);
        const def = res.data.definition_json || {};

        if (def.nodes && def.nodes.length > 0) {
          const loadedNodes = def.nodes.map((n: Node) => ({
            ...n,
            data: {
              ...n.data,
              onDelete: handleDeleteNode
            }
          }));
          setNodes(loadedNodes);
          // Apply styled edges with condition colors
          const styledEdges = (def.edges || []).map((e: Edge) => {
            const condition = ((e.data as any)?.condition as string) || e.sourceHandle || 'Succeeded';
            const prop = getConditionEdgeProperties(condition);
            return {
              ...e,
              animated: true,
              label: prop.label,
              data: { condition: prop.condition },
              style: { stroke: prop.color, strokeWidth: 2.5 },
              labelStyle: { fill: prop.color, fontWeight: 600, fontSize: 10 },
              labelBgStyle: { fill: '#0f172a', rx: 4, stroke: '#334155' }
            };
          });
          setEdges(styledEdges);
        } else if (def.activities && def.activities.length > 0) {
          // Convert activities to nodes
          const generatedNodes: Node[] = def.activities.map((act: any, idx: number) => ({
            id: act.id,
            type: 'activityNode',
            position: { x: 150 + idx * 290, y: 150 },
            data: {
              label: act.name,
              activityType: act.type,
              state: act.state || 'Active',
              config: act.config || {},
              retry_policy: act.retry_policy,
              onDelete: handleDeleteNode
            }
          }));

          const generatedEdges: Edge[] = [];
          def.activities.forEach((act: any) => {
            (act.depends_on || []).forEach((dep: any) => {
              const parentId = typeof dep === 'string' ? dep : dep.activity_id;
              const cond = typeof dep === 'string' ? 'Succeeded' : (dep.condition || 'Succeeded');
              const prop = getConditionEdgeProperties(cond);

              generatedEdges.push({
                id: `e-${parentId}-${act.id}-${prop.sourceHandle}`,
                source: parentId,
                target: act.id,
                sourceHandle: prop.sourceHandle,
                targetHandle: 'input',
                animated: true,
                label: prop.label,
                data: { condition: prop.condition },
                style: { stroke: prop.color, strokeWidth: 2.5 },
                labelStyle: { fill: prop.color, fontWeight: 600, fontSize: 10 },
                labelBgStyle: { fill: '#0f172a', rx: 4, stroke: '#334155' }
              });
            });
          });

          setNodes(generatedNodes);
          setEdges(generatedEdges);
        } else {
          setNodes([]);
          setEdges([]);
        }
      } catch (err) {
        console.error('Failed to load pipeline', err);
      }
    };
    loadPipe();
  }, [selectedPipelineId, handleDeleteNode]);

  const onConnect = useCallback(
    (params: Connection) => {
      const handleType = params.sourceHandle || 'success';
      const prop = getConditionEdgeProperties(handleType);

      const newEdge: Edge = {
        id: `e-${params.source}-${params.target}-${prop.sourceHandle}`,
        source: params.source,
        target: params.target,
        sourceHandle: params.sourceHandle,
        targetHandle: params.targetHandle,
        animated: true,
        label: prop.label,
        data: { condition: prop.condition },
        style: { stroke: prop.color, strokeWidth: 2.5 },
        labelStyle: { fill: prop.color, fontWeight: 600, fontSize: 10 },
        labelBgStyle: { fill: '#0f172a', rx: 4, stroke: '#334155' }
      };

      setEdges((eds) => addEdge(newEdge, eds));
    },
    [setEdges]
  );

  const onEdgeClick = (_: any, edge: Edge) => {
    // Cycle condition on edge click: Succeeded -> Failed -> Completed -> Skipped -> Succeeded
    const current = edge.data?.condition || 'Succeeded';
    let nextCond = 'Failed';
    if (current === 'Failed') nextCond = 'Completed';
    else if (current === 'Completed') nextCond = 'Skipped';
    else if (current === 'Skipped') nextCond = 'Succeeded';

    const prop = getConditionEdgeProperties(nextCond);

    setEdges((eds) =>
      eds.map((e) => {
        if (e.id === edge.id) {
          return {
            ...e,
            label: prop.label,
            sourceHandle: prop.sourceHandle,
            data: { condition: prop.condition },
            style: { stroke: prop.color, strokeWidth: 2.5 },
            labelStyle: { fill: prop.color, fontWeight: 600, fontSize: 10 },
            labelBgStyle: { fill: '#0f172a', rx: 4, stroke: '#334155' }
          };
        }
        return e;
      })
    );
  };

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
          state: 'Active',
          config: {
            source: {},
            destination: {},
            rules: []
          },
          retry_policy: {
            max_retries: 0,
            retry_interval_seconds: 2
          },
          onDelete: handleDeleteNode
        },
      };

      setNodes((nds) => nds.concat(newNode));
      setSelectedNode(newNode);
    },
    [setNodes, handleDeleteNode]
  );

  const handleNodeClick = (_: any, node: Node) => {
    setSelectedNode(node);
  };

  const handleUpdateNode = (nodeId: string, updatedData: any) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          const updated = {
            ...n,
            data: {
              ...updatedData,
              onDelete: handleDeleteNode
            }
          };
          setSelectedNode(updated);
          return updated;
        }
        return n;
      })
    );
  };

  const handleUpdateDependencyCondition = (edgeId: string, newCondition: string) => {
    const prop = getConditionEdgeProperties(newCondition);
    setEdges((eds) =>
      eds.map((e) => {
        if (e.id === edgeId) {
          return {
            ...e,
            label: prop.label,
            sourceHandle: prop.sourceHandle,
            data: { condition: prop.condition },
            style: { stroke: prop.color, strokeWidth: 2.5 },
            labelStyle: { fill: prop.color, fontWeight: 600, fontSize: 10 },
            labelBgStyle: { fill: '#0f172a', rx: 4, stroke: '#334155' }
          };
        }
        return e;
      })
    );
  };

  const constructPipelineDefinition = () => {
    const activities = nodes.map((n) => {
      const incomingEdges = edges.filter((e) => e.target === n.id);
      const depends_on = incomingEdges.map((e) => {
        const cond = e.data?.condition || (
          e.sourceHandle === 'failure' ? 'Failed' :
          e.sourceHandle === 'completion' ? 'Completed' :
          e.sourceHandle === 'skipped' ? 'Skipped' : 'Succeeded'
        );
        return {
          activity_id: e.source,
          condition: cond
        };
      });

      return {
        id: n.id,
        name: n.data.label,
        type: n.data.activityType,
        state: n.data.state || 'Active',
        retry_policy: n.data.retry_policy,
        depends_on,
        config: n.data.config || {}
      };
    });

    const cleanNodes = nodes.map((n) => {
      const { onDelete, ...cleanData } = (n.data || {}) as any;
      return {
        ...n,
        data: cleanData
      };
    });

    return {
      parameters: pipeline?.definition_json?.parameters || {},
      variables: pipeline?.definition_json?.variables || { high_watermark: '1970-01-01 00:00:00' },
      activities,
      nodes: cleanNodes,
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
      const def = constructPipelineDefinition();
      await api.put(`/pipelines/${selectedPipelineId}`, { definition_json: def });
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
          {selectedNode && (
            <button
              onClick={() => handleDeleteNode(selectedNode.id)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 transition font-medium"
              title="Delete Selected Activity"
            >
              <Trash2 className="h-3.5 w-3.5 text-rose-400" />
              <span>Delete Activity</span>
            </button>
          )}

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
            onEdgeClick={onEdgeClick}
            onNodesDelete={(deleted) => deleted.forEach((n) => handleDeleteNode(n.id))}
            deleteKeyCode={['Backspace', 'Delete']}
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
            allNodes={nodes}
            allEdges={edges}
            onUpdateNode={handleUpdateNode}
            onUpdateDependencyCondition={handleUpdateDependencyCondition}
            onDeleteNode={handleDeleteNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
};
