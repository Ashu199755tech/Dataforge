import React, { useState, useEffect } from 'react';
import { 
  X, 
  GitBranch, 
  Plus, 
  Check, 
  RefreshCw, 
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import api from '../../api/client';

interface GitBranchInfo {
  name: string;
  is_current: boolean;
  is_default: boolean;
  commit_hash?: string;
  commit_message?: string;
  author?: string;
}

interface GitBranchModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  currentBranch: string;
  onSuccess: (newBranch: string) => void;
}

export const GitBranchModal: React.FC<GitBranchModalProps> = ({
  isOpen,
  onClose,
  projectId,
  currentBranch,
  onSuccess
}) => {
  const [branches, setBranches] = useState<GitBranchInfo[]>([]);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');
  const [sourceBranch, setSourceBranch] = useState(currentBranch || 'main');
  const [isLoading, setIsLoading] = useState(false);
  const [isActionInProgress, setIsActionInProgress] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && projectId) {
      loadBranches();
    }
  }, [isOpen, projectId]);

  const loadBranches = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.get<GitBranchInfo[]>(`/git/branches?project_id=${projectId}`);
      setBranches(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load repository branches');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSwitchBranch = async (branchName: string) => {
    if (branchName === currentBranch) return;

    try {
      setIsActionInProgress(true);
      setError(null);
      await api.post(`/git/branch?project_id=${projectId}`, {
        branch_name: branchName,
        create_new: false
      });
      onSuccess(branchName);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to switch branch');
    } finally {
      setIsActionInProgress(false);
    }
  };

  const handleCreateBranch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBranchName.trim()) {
      setError('Branch name is required');
      return;
    }

    try {
      setIsActionInProgress(true);
      setError(null);
      const formattedBranch = newBranchName.trim().replace(/\s+/g, '-');
      await api.post(`/git/branch?project_id=${projectId}`, {
        branch_name: formattedBranch,
        create_new: true,
        source_branch: sourceBranch
      });
      onSuccess(formattedBranch);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create branch');
    } finally {
      setIsActionInProgress(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto cursor-pointer"
      onClick={onClose}
    >
      <div 
        className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full shadow-2xl overflow-hidden cursor-default"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-500/20 text-brand-400 border border-brand-500/30">
              <GitBranch className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Switch or Create Branch</h2>
              <p className="text-[11px] text-slate-400">Current active branch: <span className="text-brand-300 font-mono">{currentBranch}</span></p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-3">
          {error && (
            <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!isCreatingNew ? (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Available Branches</span>
                <button
                  onClick={() => setIsCreatingNew(true)}
                  className="text-xs text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New Branch
                </button>
              </div>

              <div className="max-h-60 overflow-y-auto space-y-1 pr-1">
                {isLoading ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-2 text-slate-400" />
                    Loading branches...
                  </div>
                ) : (
                  branches.map((b) => {
                    const isSelected = b.name === currentBranch;
                    return (
                      <button
                        key={b.name}
                        onClick={() => handleSwitchBranch(b.name)}
                        disabled={isActionInProgress}
                        className={`w-full flex items-center justify-between p-2.5 rounded-lg text-xs transition ${
                          isSelected
                            ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
                            : 'hover:bg-slate-800/60 text-slate-300 border border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-2 font-mono">
                          <GitBranch className={`h-3.5 w-3.5 ${isSelected ? 'text-brand-400' : 'text-slate-500'}`} />
                          <span>{b.name}</span>
                          {b.is_default && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                              default
                            </span>
                          )}
                        </div>
                        {isSelected && <Check className="h-4 w-4 text-brand-400" />}
                      </button>
                    );
                  })
                )}
              </div>
            </>
          ) : (
            <form onSubmit={handleCreateBranch} className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">
                  New Branch Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="feature/data-enrichment"
                  value={newBranchName}
                  onChange={(e) => setNewBranchName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">
                  Base Branch (Source)
                </label>
                <select
                  value={sourceBranch}
                  onChange={(e) => setSourceBranch(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 font-mono"
                >
                  {branches.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name} {b.is_default ? '(default)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreatingNew(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-white rounded-lg transition"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isActionInProgress || !newBranchName.trim()}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-1.5 transition"
                >
                  {isActionInProgress ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Plus className="h-3.5 w-3.5" />
                      Create & Switch
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
