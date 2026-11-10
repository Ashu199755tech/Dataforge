import React, { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';
import { 
  Rocket, 
  GitBranch, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Clock, 
  RotateCcw, 
  FileCode, 
  Play, 
  Plus, 
  RefreshCw, 
  ArrowRight, 
  ShieldCheck, 
  Layers, 
  Copy, 
  Download, 
  ExternalLink,
  ChevronRight,
  Database,
  Terminal,
  X,
  ArrowLeft
} from 'lucide-react';
import api from '../api/client';

interface DeploymentRecord {
  id: string;
  project_id: string;
  source_environment: string;
  target_environment: string;
  bundle_version: string;
  status: 'PendingApproval' | 'Approved' | 'Rejected' | 'Deployed' | 'Failed' | 'RolledBack';
  pipeline_ids: string[];
  dataset_ids: string[];
  trigger_ids: string[];
  parameter_substitutions: Record<string, any>;
  manifest_json: Record<string, any>;
  dry_run_diff: Record<string, any>;
  requested_by_id?: string;
  approved_by_id?: string;
  approval_comment?: string;
  deployed_at?: string;
  created_at: string;
  updated_at: string;
}

interface DryRunResponse {
  source_environment: string;
  target_environment: string;
  can_deploy: boolean;
  warnings: string[];
  diff_summary: Record<string, number>;
  asset_diffs: any[];
  parameter_substitutions: Record<string, any>;
}

export const DeploymentsPage: React.FC = () => {
  const { activeProject } = useAppStore();

  const [activeTab, setActiveTab] = useState<'history' | 'approvals' | 'cicd'>('history');
  const [deployments, setDeployments] = useState<DeploymentRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New Promotion Wizard Modal State
  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [sourceEnv, setSourceEnv] = useState('Development');
  const [targetEnv, setTargetEnv] = useState('Production');
  const [bundleVersion, setBundleVersion] = useState('v1.0.0');
  const [selectedPipelines, setSelectedPipelines] = useState<string[]>([]);
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const [selectedTriggers, setSelectedTriggers] = useState<string[]>([]);
  const [paramOverrides, setParamOverrides] = useState<{ key: string; value: string }[]>([
    { key: 'target_database_host', value: 'prod-sql.enterprise.internal' },
    { key: 'storage_bucket_override', value: 'corp-datalake-prod' }
  ]);
  const [dryRunReport, setDryRunReport] = useState<DryRunResponse | null>(null);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);

  // Available metadata in project
  const [availablePipelines, setAvailablePipelines] = useState<{ id: string; name: string }[]>([]);
  const [availableDatasets, setAvailableDatasets] = useState<{ id: string; name: string; type: string }[]>([]);
  const [availableTriggers, setAvailableTriggers] = useState<{ id: string; name: string; type: string }[]>([]);

  // Approval review modal state
  const [reviewDeployment, setReviewDeployment] = useState<DeploymentRecord | null>(null);
  const [approvalComment, setApprovalComment] = useState('');
  const [isActionSubmitting, setIsActionSubmitting] = useState(false);

  // CI/CD Workflow state
  const [ciWorkflowContent, setCiWorkflowContent] = useState('');
  const [copiedCiYaml, setCopiedCiYaml] = useState(false);

  const fetchDeployments = useCallback(async () => {
    if (!activeProject?.id) return;
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.get<DeploymentRecord[]>(`/deployments?project_id=${activeProject.id}`);
      setDeployments(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch release history');
    } finally {
      setIsLoading(false);
    }
  }, [activeProject?.id]);

  const loadProjectAssets = useCallback(async () => {
    if (!activeProject?.id) return;
    try {
      // 1. Pipelines
      const pipeRes = await api.get(`/pipelines?project_id=${activeProject.id}`);
      setAvailablePipelines(pipeRes.data.map((p: any) => ({ id: p.id, name: p.name })));
      setSelectedPipelines(pipeRes.data.map((p: any) => p.id));

      // 2. Datasets
      try {
        const dsRes = await api.get(`/datasets?project_id=${activeProject.id}`);
        setAvailableDatasets(dsRes.data.map((d: any) => ({ id: d.id, name: d.name, type: d.dataset_type })));
        setSelectedDatasets(dsRes.data.map((d: any) => d.id));
      } catch (e) {
        console.warn('Datasets fetch failed', e);
      }

      // 3. Triggers
      try {
        const trgRes = await api.get(`/triggers?project_id=${activeProject.id}`);
        setAvailableTriggers(trgRes.data.map((t: any) => ({ id: t.id, name: t.name, type: t.trigger_type })));
        setSelectedTriggers(trgRes.data.map((t: any) => t.id));
      } catch (e) {
        console.warn('Triggers fetch failed', e);
      }
    } catch (err) {
      console.warn('Failed to load project assets for promotion', err);
    }
  }, [activeProject?.id]);

  const fetchCiWorkflow = useCallback(async () => {
    if (!activeProject?.id) return;
    try {
      const res = await api.get(`/deployments/cicd-template?project_id=${activeProject.id}`);
      setCiWorkflowContent(res.data.content);
    } catch (e) {
      console.warn('Failed to load CI/CD workflow template', e);
    }
  }, [activeProject?.id]);

  useEffect(() => {
    fetchDeployments();
    loadProjectAssets();
    fetchCiWorkflow();
  }, [fetchDeployments, loadProjectAssets, fetchCiWorkflow]);

  const handleDryRun = async () => {
    if (!activeProject?.id) return;
    try {
      setIsDryRunning(true);
      setError(null);
      const paramsObj: Record<string, any> = {};
      paramOverrides.forEach(p => {
        if (p.key.trim()) paramsObj[p.key.trim()] = p.value;
      });

      const res = await api.post<DryRunResponse>(`/deployments/dry-run?project_id=${activeProject.id}`, {
        source_environment: sourceEnv,
        target_environment: targetEnv,
        pipeline_ids: selectedPipelines,
        dataset_ids: selectedDatasets,
        trigger_ids: selectedTriggers,
        parameter_substitutions: paramsObj
      });
      setDryRunReport(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Dry-run pre-validation failed');
    } finally {
      setIsDryRunning(false);
    }
  };

  const handleCreateDeployment = async () => {
    if (!activeProject?.id) return;
    try {
      setIsDeploying(true);
      setError(null);
      const paramsObj: Record<string, any> = {};
      paramOverrides.forEach(p => {
        if (p.key.trim()) paramsObj[p.key.trim()] = p.value;
      });

      await api.post(`/deployments?project_id=${activeProject.id}`, {
        source_environment: sourceEnv,
        target_environment: targetEnv,
        bundle_version: bundleVersion.trim() || `v${Date.now()}`,
        pipeline_ids: selectedPipelines,
        dataset_ids: selectedDatasets,
        trigger_ids: selectedTriggers,
        parameter_substitutions: paramsObj,
        notes: `Release promotion from ${sourceEnv} to ${targetEnv}`
      });

      setIsPromoteModalOpen(false);
      setDryRunReport(null);
      await fetchDeployments();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Deployment creation failed');
    } finally {
      setIsDeploying(false);
    }
  };

  const handleApprove = async (depId: string) => {
    try {
      setIsActionSubmitting(true);
      await api.post(`/deployments/${depId}/approve`, {
        approved: true,
        comment: approvalComment || 'Approved for release'
      });
      setReviewDeployment(null);
      setApprovalComment('');
      await fetchDeployments();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Approval failed');
    } finally {
      setIsActionSubmitting(false);
    }
  };

  const handleReject = async (depId: string) => {
    try {
      setIsActionSubmitting(true);
      await api.post(`/deployments/${depId}/reject`, {
        approved: false,
        comment: approvalComment || 'Rejected by release manager'
      });
      setReviewDeployment(null);
      setApprovalComment('');
      await fetchDeployments();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Rejection failed');
    } finally {
      setIsActionSubmitting(false);
    }
  };

  const handleRollback = async (dep: DeploymentRecord) => {
    if (!window.confirm(`Are you sure you want to rollback release ${dep.bundle_version} in ${dep.target_environment}? This will restore the prior snapshot.`)) {
      return;
    }

    try {
      setIsLoading(true);
      await api.post(`/deployments/${dep.id}/rollback`);
      await fetchDeployments();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Rollback failed');
    } finally {
      setIsLoading(false);
    }
  };

  const pendingApprovals = deployments.filter(d => d.status === 'PendingApproval');

  const getStatusBadge = (status: DeploymentRecord['status']) => {
    switch (status) {
      case 'Deployed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" /> Deployed
          </span>
        );
      case 'PendingApproval':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20 animate-pulse">
            <Clock className="h-3 w-3" /> Pending Approval
          </span>
        );
      case 'Approved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
            <ShieldCheck className="h-3 w-3" /> Approved
          </span>
        );
      case 'Rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle className="h-3 w-3" /> Rejected
          </span>
        );
      case 'RolledBack':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <RotateCcw className="h-3 w-3" /> Rolled Back
          </span>
        );
      case 'Failed':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="h-3 w-3" /> Failed
          </span>
        );
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-start gap-3">
          <button
            onClick={() => {
              if (window.history.length > 1) {
                window.history.back();
              } else {
                useAppStore.getState().setCurrentTab('dashboard');
              }
            }}
            className="p-2 mt-1 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition shadow-sm flex items-center justify-center group"
            title="Go back (Alt + Left Arrow)"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
          </button>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 text-white shadow-lg shadow-brand-500/20">
              <Rocket className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                Deployments & CI/CD
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-normal border border-slate-700">
                  Release Management
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Multi-environment promotion, dry-run DAG pre-validation, approval governance, and automated CI/CD
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchDeployments}
            disabled={isLoading}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Refresh Releases"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => {
              loadProjectAssets();
              setIsPromoteModalOpen(true);
            }}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-2 transition"
          >
            <Plus className="h-4 w-4" />
            Promote Release
          </button>
        </div>
      </div>

      {/* Multi-Environment Visual Promotion Pipeline */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center justify-between">
          <span>Enterprise Multi-Environment Lifecycle</span>
          <span className="text-brand-400 font-mono text-[11px] normal-case">Controlled Promotion Gates</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Dev */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3.5 relative overflow-hidden group">
            <div className="h-1 w-full bg-cyan-500 absolute top-0 left-0" />
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-white">Development</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 font-mono border border-cyan-500/20">
                Direct
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
              Active engineering environment with direct workspace authoring and live debugging.
            </p>
            <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-cyan-400" /> Auto-validated DAGs
            </div>
          </div>

          {/* Test / QA */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3.5 relative overflow-hidden group">
            <div className="h-1 w-full bg-blue-500 absolute top-0 left-0" />
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-white">Test / QA</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono border border-blue-500/20">
                Automated
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
              Synthetic data validation, schema drift check, and automated integration test runs.
            </p>
            <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-blue-400" /> CI/CD Automated
            </div>
          </div>

          {/* Staging */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3.5 relative overflow-hidden group">
            <div className="h-1 w-full bg-indigo-500 absolute top-0 left-0" />
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-white">Staging / UAT</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 font-mono border border-amber-500/20">
                Approval Gate
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
              Pre-production mirror with sanitized enterprise datasets and performance benchmarking.
            </p>
            <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
              <Clock className="h-3 w-3 text-amber-400" /> Reviewer Required
            </div>
          </div>

          {/* Production */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3.5 relative overflow-hidden group">
            <div className="h-1 w-full bg-emerald-500 absolute top-0 left-0" />
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-white">Production</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                Restricted
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed mb-3">
              Mission-critical live analytical pipelines with immutable audit logs and 1-click rollback.
            </p>
            <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
              <ShieldCheck className="h-3 w-3 text-emerald-400" /> Strict Governance
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'history'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Rocket className="h-3.5 w-3.5" />
          Release History ({deployments.length})
        </button>

        <button
          onClick={() => setActiveTab('approvals')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition flex items-center gap-2 relative ${
            activeTab === 'approvals'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          Pending Approvals
          {pendingApprovals.length > 0 && (
            <span className="h-4 px-1.5 rounded-full bg-amber-500 text-slate-950 text-[10px] font-bold flex items-center justify-center">
              {pendingApprovals.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('cicd')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'cicd'
              ? 'border-brand-500 text-brand-400 bg-brand-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCode className="h-3.5 w-3.5" />
          CI/CD Automation Workflow
        </button>
      </div>

      {/* Tab 1: Release History Table */}
      {activeTab === 'history' && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Release Version</th>
                  <th className="py-3 px-4">Promotion Path</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Assets Included</th>
                  <th className="py-3 px-4">Created / Deployed</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {deployments.length > 0 ? (
                  deployments.map((dep) => (
                    <tr key={dep.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 px-4">
                        <div className="font-mono font-semibold text-white flex items-center gap-1.5">
                          <Rocket className="h-3.5 w-3.5 text-brand-400" />
                          {dep.bundle_version}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">ID: {dep.id.slice(0, 8)}...</div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 font-medium">
                          <span className="text-slate-300">{dep.source_environment}</span>
                          <ArrowRight className="h-3 w-3 text-slate-500" />
                          <span className="text-brand-400 font-semibold">{dep.target_environment}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        {getStatusBadge(dep.status)}
                      </td>
                      <td className="py-3 px-4 text-slate-400 text-[11px]">
                        <div>{dep.pipeline_ids?.length || 0} Pipelines</div>
                        <div className="text-slate-500">{dep.dataset_ids?.length || 0} Datasets, {dep.trigger_ids?.length || 0} Triggers</div>
                      </td>
                      <td className="py-3 px-4 text-slate-400 text-[11px]">
                        <div>{new Date(dep.created_at).toLocaleDateString()} {new Date(dep.created_at).toLocaleTimeString()}</div>
                        {dep.deployed_at && (
                          <div className="text-emerald-400 text-[10px]">
                            Deployed: {new Date(dep.deployed_at).toLocaleTimeString()}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {dep.status === 'PendingApproval' && (
                            <button
                              onClick={() => setReviewDeployment(dep)}
                              className="px-2.5 py-1 text-xs font-medium text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-lg transition"
                            >
                              Review & Gate
                            </button>
                          )}

                          {dep.status === 'Deployed' && (
                            <button
                              onClick={() => handleRollback(dep)}
                              className="px-2.5 py-1 text-xs font-medium text-purple-300 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 rounded-lg transition flex items-center gap-1"
                              title="Restore previous environment state"
                            >
                              <RotateCcw className="h-3 w-3" />
                              Rollback
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-500 text-xs">
                      No release promotion history found. Click "Promote Release" to deploy changes across environments.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Pending Approvals */}
      {activeTab === 'approvals' && (
        <div className="space-y-4">
          {pendingApprovals.length > 0 ? (
            pendingApprovals.map((dep) => (
              <div key={dep.id} className="bg-slate-900/80 border border-amber-500/30 rounded-xl p-5 shadow-xl space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <Clock className="h-4 w-4" />
                    </span>
                    <div>
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        Release {dep.bundle_version} Promotion
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-normal">
                          {dep.source_environment} &rarr; {dep.target_environment}
                        </span>
                      </h3>
                      <p className="text-[11px] text-slate-400">
                        Requested at {new Date(dep.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleReject(dep.id)}
                      disabled={isActionSubmitting}
                      className="px-3 py-1.5 text-xs font-medium text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-lg transition flex items-center gap-1.5"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </button>
                    <button
                      onClick={() => handleApprove(dep.id)}
                      disabled={isActionSubmitting}
                      className="px-4 py-1.5 text-xs font-semibold text-emerald-300 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 rounded-lg transition flex items-center gap-1.5 shadow-lg shadow-emerald-500/20"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Approve & Deploy
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 font-semibold mb-1">Pipelines ({dep.pipeline_ids?.length || 0})</div>
                    <div className="text-slate-300 font-mono text-[11px] truncate">
                      {dep.pipeline_ids?.join(', ') || 'None'}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 font-semibold mb-1">Reusable Datasets ({dep.dataset_ids?.length || 0})</div>
                    <div className="text-slate-300 font-mono text-[11px] truncate">
                      {dep.dataset_ids?.join(', ') || 'None'}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 font-semibold mb-1">Parameter Overrides</div>
                    <div className="text-slate-300 font-mono text-[11px]">
                      {Object.keys(dep.parameter_substitutions || {}).length} variables mapped
                    </div>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-12 text-center text-slate-500 text-xs">
              <ShieldCheck className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
              All deployment gates are cleared. No pending approvals requiring sign-off.
            </div>
          )}
        </div>
      )}

      {/* Tab 3: CI/CD Automation Workflow */}
      {activeTab === 'cicd' && (
        <div className="space-y-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-brand-400" />
                  GitHub Actions Declarative Pipeline
                </h3>
                <p className="text-xs text-slate-400">
                  Automate deployments directly from your repository on merge to main or release tags
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(ciWorkflowContent);
                    setCopiedCiYaml(true);
                    setTimeout(() => setCopiedCiYaml(false), 2000);
                  }}
                  className="px-3 py-1.5 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition flex items-center gap-1.5"
                >
                  <Copy className="h-3.5 w-3.5 text-brand-400" />
                  {copiedCiYaml ? 'Copied to Clipboard!' : 'Copy Workflow YAML'}
                </button>
              </div>
            </div>

            <div className="bg-slate-950 rounded-lg p-4 border border-slate-800 overflow-x-auto">
              <pre className="text-slate-300 font-mono text-xs leading-relaxed">
                {ciWorkflowContent || '# Loading workflow template...'}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Promote Release Wizard Modal */}
      {isPromoteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-3xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-brand-500/20 text-brand-400 border border-brand-500/30">
                  <Rocket className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-white">Release Promotion Wizard</h2>
                  <p className="text-xs text-slate-400">Pre-validate DAG integrity and promote assets to target environment</p>
                </div>
              </div>
              <button
                onClick={() => setIsPromoteModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5 text-xs">
              {error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Environments */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-slate-300 font-medium">Source Environment</label>
                  <select
                    value={sourceEnv}
                    onChange={(e) => setSourceEnv(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-brand-500"
                  >
                    <option value="Development">Development (Dev)</option>
                    <option value="Test">Test / QA</option>
                    <option value="Staging">Staging</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-slate-300 font-medium">Target Environment</label>
                  <select
                    value={targetEnv}
                    onChange={(e) => setTargetEnv(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-brand-500"
                  >
                    <option value="Test">Test / QA (Automated)</option>
                    <option value="Staging">Staging (Approval Gate)</option>
                    <option value="Production">Production (Approval Gate)</option>
                  </select>
                </div>
              </div>

              {/* Bundle Version */}
              <div className="space-y-1.5">
                <label className="text-slate-300 font-medium">Bundle Release Version</label>
                <input
                  type="text"
                  required
                  value={bundleVersion}
                  onChange={(e) => setBundleVersion(e.target.value)}
                  placeholder="v1.2.0"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-brand-500"
                />
              </div>

              {/* Asset Selection */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300 font-medium">Select Assets to Promote</span>
                  <div className="flex items-center gap-2 text-[11px] text-brand-400">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedPipelines(availablePipelines.map(p => p.id));
                        setSelectedDatasets(availableDatasets.map(d => d.id));
                        setSelectedTriggers(availableTriggers.map(t => t.id));
                      }}
                      className="hover:underline"
                    >
                      Select All
                    </button>
                    <span>&bull;</span>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedPipelines([]);
                        setSelectedDatasets([]);
                        setSelectedTriggers([]);
                      }}
                      className="hover:underline text-slate-400"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {/* Pipelines */}
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2 max-h-40 overflow-y-auto">
                    <div className="font-semibold text-slate-400 text-[11px]">Pipelines ({availablePipelines.length})</div>
                    {availablePipelines.map(p => (
                      <label key={p.id} className="flex items-center gap-2 cursor-pointer hover:text-white text-slate-300">
                        <input
                          type="checkbox"
                          checked={selectedPipelines.includes(p.id)}
                          onChange={(e) => {
                            if (e.target.checked) setSelectedPipelines([...selectedPipelines, p.id]);
                            else setSelectedPipelines(selectedPipelines.filter(id => id !== p.id));
                          }}
                          className="rounded border-slate-700 text-brand-500"
                        />
                        <span className="truncate">{p.name}</span>
                      </label>
                    ))}
                  </div>

                  {/* Datasets */}
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2 max-h-40 overflow-y-auto">
                    <div className="font-semibold text-slate-400 text-[11px]">Datasets ({availableDatasets.length})</div>
                    {availableDatasets.map(d => (
                      <label key={d.id} className="flex items-center gap-2 cursor-pointer hover:text-white text-slate-300">
                        <input
                          type="checkbox"
                          checked={selectedDatasets.includes(d.id)}
                          onChange={(e) => {
                            if (e.target.checked) setSelectedDatasets([...selectedDatasets, d.id]);
                            else setSelectedDatasets(selectedDatasets.filter(id => id !== d.id));
                          }}
                          className="rounded border-slate-700 text-brand-500"
                        />
                        <span className="truncate">{d.name}</span>
                      </label>
                    ))}
                  </div>

                  {/* Triggers */}
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2 max-h-40 overflow-y-auto">
                    <div className="font-semibold text-slate-400 text-[11px]">Triggers ({availableTriggers.length})</div>
                    {availableTriggers.map(t => (
                      <label key={t.id} className="flex items-center gap-2 cursor-pointer hover:text-white text-slate-300">
                        <input
                          type="checkbox"
                          checked={selectedTriggers.includes(t.id)}
                          onChange={(e) => {
                            if (e.target.checked) setSelectedTriggers([...selectedTriggers, t.id]);
                            else setSelectedTriggers(selectedTriggers.filter(id => id !== t.id));
                          }}
                          className="rounded border-slate-700 text-brand-500"
                        />
                        <span className="truncate">{t.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* Parameter Substitutions */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300 font-medium">Target Environment Parameter Substitutions</span>
                  <button
                    type="button"
                    onClick={() => setParamOverrides([...paramOverrides, { key: '', value: '' }])}
                    className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add Variable
                  </button>
                </div>

                <div className="space-y-2">
                  {paramOverrides.map((param, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="Variable Key (e.g., db_host)"
                        value={param.key}
                        onChange={(e) => {
                          const updated = [...paramOverrides];
                          updated[idx].key = e.target.value;
                          setParamOverrides(updated);
                        }}
                        className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                      />
                      <input
                        type="text"
                        placeholder="Target Value Override"
                        value={param.value}
                        onChange={(e) => {
                          const updated = [...paramOverrides];
                          updated[idx].value = e.target.value;
                          setParamOverrides(updated);
                        }}
                        className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => setParamOverrides(paramOverrides.filter((_, i) => i !== idx))}
                        className="text-slate-500 hover:text-rose-400 p-1 rounded"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Dry-Run Pre-Validation Button & Report */}
              <div className="pt-2 border-t border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-slate-300">DAG Pre-Validation & Impact Analysis</div>
                    <div className="text-[11px] text-slate-500">Check for circular loops, missing references, and compute diffs</div>
                  </div>
                  <button
                    type="button"
                    onClick={handleDryRun}
                    disabled={isDryRunning}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 flex items-center gap-1.5 font-medium transition"
                  >
                    <Play className={`h-3.5 w-3.5 text-brand-400 ${isDryRunning ? 'animate-spin' : ''}`} />
                    Run Pre-Validation
                  </button>
                </div>

                {dryRunReport && (
                  <div className={`p-4 rounded-lg border ${
                    dryRunReport.can_deploy 
                      ? 'bg-emerald-500/10 border-emerald-500/30' 
                      : 'bg-rose-500/10 border-rose-500/30'
                  } space-y-2`}>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white flex items-center gap-2">
                        {dryRunReport.can_deploy ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-400" />
                        )}
                        Pre-Validation {dryRunReport.can_deploy ? 'Passed' : 'Failed'}
                      </span>
                      <span className="font-mono text-[11px] text-slate-300">
                        Diff: {JSON.stringify(dryRunReport.diff_summary)}
                      </span>
                    </div>

                    {dryRunReport.warnings.length > 0 && (
                      <div className="space-y-1">
                        {dryRunReport.warnings.map((w, idx) => (
                          <div key={idx} className="text-amber-300 text-[11px] flex items-center gap-1.5">
                            <AlertTriangle className="h-3 w-3 shrink-0" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between">
              <span className="text-slate-500 text-[11px]">
                {targetEnv === 'Production' || targetEnv === 'Staging' ? 'Requires Approval Gate' : 'Automatic Direct Promotion'}
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsPromoteModalOpen(false)}
                  className="px-3 py-1.5 text-slate-400 hover:text-white rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreateDeployment}
                  disabled={isDeploying || (selectedPipelines.length === 0 && selectedDatasets.length === 0)}
                  className="px-4 py-1.5 font-semibold text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-2 transition"
                >
                  {isDeploying ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      Promoting...
                    </>
                  ) : (
                    <>
                      <Rocket className="h-3.5 w-3.5" />
                      Schedule Promotion
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Review & Gate Modal */}
      {reviewDeployment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-brand-400" />
                Release Review Gate
              </h3>
              <button onClick={() => setReviewDeployment(null)} className="text-slate-400 hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Release <span className="text-white font-mono font-semibold">{reviewDeployment.bundle_version}</span> targeted for <span className="text-brand-300 font-semibold">{reviewDeployment.target_environment}</span>.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Approval / Rejection Comment</label>
              <textarea
                rows={3}
                placeholder="e.g., Verified in UAT, all schema migrations and data quality gates passed."
                value={approvalComment}
                onChange={(e) => setApprovalComment(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => handleReject(reviewDeployment.id)}
                disabled={isActionSubmitting}
                className="px-3 py-1.5 text-xs font-medium text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-lg transition"
              >
                Reject Release
              </button>
              <button
                type="button"
                onClick={() => handleApprove(reviewDeployment.id)}
                disabled={isActionSubmitting}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow-lg shadow-emerald-600/30 transition flex items-center gap-1.5"
              >
                Approve & Deploy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
