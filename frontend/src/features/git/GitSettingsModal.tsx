import React, { useState, useEffect } from 'react';
import { 
  X, 
  GitBranch, 
  FolderGit2, 
  Lock, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Trash2,
  ExternalLink,
  ShieldAlert
} from 'lucide-react';
import api from '../../api/client';

interface GitRepositoryResponse {
  id: string;
  project_id: string;
  name: string;
  provider: string;
  repo_url: string;
  default_branch: string;
  current_branch: string;
  root_folder: string;
  auth_type: string;
  last_commit_hash?: string;
  last_sync_at?: string;
  sync_status: string;
  is_connected: boolean;
}

interface GitSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  currentRepo: GitRepositoryResponse | null;
  onSuccess: () => void;
}

export const GitSettingsModal: React.FC<GitSettingsModalProps> = ({
  isOpen,
  onClose,
  projectId,
  currentRepo,
  onSuccess
}) => {
  const [provider, setProvider] = useState('github');
  const [repoUrl, setRepoUrl] = useState('');
  const [defaultBranch, setDefaultBranch] = useState('main');
  const [rootFolder, setRootFolder] = useState('/');
  const [token, setToken] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (currentRepo) {
      setProvider(currentRepo.provider || 'github');
      setRepoUrl(currentRepo.repo_url || '');
      setDefaultBranch(currentRepo.default_branch || 'main');
      setRootFolder(currentRepo.root_folder || '/');
      setToken('');
    } else {
      setProvider('github');
      setRepoUrl('');
      setDefaultBranch('main');
      setRootFolder('/');
      setToken('');
    }
  }, [currentRepo, isOpen]);

  if (!isOpen) return null;

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) {
      setError('Repository URL is required');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      await api.post(`/git/connect?project_id=${projectId}`, {
        repo_url: repoUrl.trim(),
        provider,
        default_branch: defaultBranch.trim() || 'main',
        current_branch: defaultBranch.trim() || 'main',
        root_folder: rootFolder.trim() || '/',
        auth_type: 'pat',
        token: token.trim() || undefined
      });
      setSuccessMessage('Git repository connected and synchronized successfully!');
      setTimeout(() => {
        setSuccessMessage(null);
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to connect Git repository');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Are you sure you want to disconnect Git source control? Local assets will remain safe in Live Mode.')) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      await api.post(`/git/disconnect?project_id=${projectId}`);
      setSuccessMessage('Git repository disconnected. Operating in Live Mode.');
      setTimeout(() => {
        setSuccessMessage(null);
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to disconnect Git repository');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-500/20 text-brand-400 border border-brand-500/30">
              <FolderGit2 className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">
                {currentRepo?.is_connected ? 'Git Repository Configuration' : 'Connect Git Repository'}
              </h2>
              <p className="text-xs text-slate-400">
                Configure source control for continuous delivery and versioning
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

        {/* Form Body */}
        <form onSubmit={handleConnect} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">
              Git Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
            >
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
              <option value="azure_devops">Azure DevOps Repos</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">
              Repository Clone URL <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="https://github.com/organization/dataforge-pipelines.git"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">
                Default Branch
              </label>
              <input
                type="text"
                required
                placeholder="main"
                value={defaultBranch}
                onChange={(e) => setDefaultBranch(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">
                Root Folder
              </label>
              <input
                type="text"
                required
                placeholder="/"
                value={rootFolder}
                onChange={(e) => setRootFolder(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-mono"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-300">
                Personal Access Token (PAT)
              </label>
              <span className="text-[10px] text-slate-500 flex items-center gap-1">
                <Lock className="h-3 w-3" /> Encrypted with AES-256
              </span>
            </div>
            <input
              type="password"
              placeholder={currentRepo?.is_connected ? "•••••••••••••••• (Leave blank to keep existing)" : "ghp_xxxxxxxxxxxxxxxxxxxx"}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-mono"
            />
            <p className="text-[11px] text-slate-500">
              Requires <code className="text-slate-400">repo</code> write scope to push pipeline JSON manifests.
            </p>
          </div>

          <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
            {currentRepo?.is_connected ? (
              <button
                type="button"
                onClick={handleDisconnect}
                disabled={isLoading}
                className="px-3 py-1.5 text-xs font-medium text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-lg border border-rose-500/30 transition flex items-center gap-1.5"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Disconnect Git
              </button>
            ) : <div />}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-2 transition"
              >
                {isLoading ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {currentRepo?.is_connected ? 'Save Configuration' : 'Connect Repository'}
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
