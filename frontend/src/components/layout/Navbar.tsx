import React, { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { 
  Database, 
  ShieldCheck, 
  Activity, 
  Bell, 
  Layers, 
  Cpu,
  GitBranch,
  FolderGit2,
  UploadCloud,
  DownloadCloud,
  Settings,
  ChevronDown,
  RefreshCw,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import api from '../../api/client';
import { GitCommitModal } from '../../features/git/GitCommitModal';
import { GitSettingsModal } from '../../features/git/GitSettingsModal';
import { GitBranchModal } from '../../features/git/GitBranchModal';

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

interface GitDiffSummary {
  branch: string;
  total_changes: number;
}

export const Navbar: React.FC = () => {
  const { activeWorkspace, activeProject } = useAppStore();

  const [gitRepo, setGitRepo] = useState<GitRepositoryResponse | null>(null);
  const [diffSummary, setDiffSummary] = useState<GitDiffSummary | null>(null);
  const [isPulling, setIsPulling] = useState(false);
  const [pullMessage, setPullMessage] = useState<string | null>(null);

  // Modals state
  const [isCommitModalOpen, setIsCommitModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isBranchModalOpen, setIsBranchModalOpen] = useState(false);

  const fetchGitStatus = useCallback(async () => {
    if (!activeProject?.id) return;
    try {
      const res = await api.get<GitRepositoryResponse>(`/git/status?project_id=${activeProject.id}`);
      setGitRepo(res.data);
      if (res.data.is_connected) {
        // Fetch diff summary
        try {
          const diffRes = await api.get<GitDiffSummary>(`/git/diff?project_id=${activeProject.id}`);
          setDiffSummary({
            branch: diffRes.data.branch,
            total_changes: diffRes.data.total_changes
          });
        } catch (e) {
          console.warn('Failed to fetch git diff summary', e);
        }
      } else {
        setDiffSummary(null);
      }
    } catch (err) {
      console.warn('Failed to fetch Git status', err);
      setGitRepo(null);
      setDiffSummary(null);
    }
  }, [activeProject?.id]);

  useEffect(() => {
    fetchGitStatus();
  }, [fetchGitStatus]);

  const handlePullSync = async () => {
    if (!activeProject?.id || !gitRepo?.is_connected) return;
    try {
      setIsPulling(true);
      await api.post(`/git/pull?project_id=${activeProject.id}`);
      setPullMessage('Synced');
      setTimeout(() => setPullMessage(null), 2000);
      fetchGitStatus();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to pull from remote');
    } finally {
      setIsPulling(false);
    }
  };

  return (
    <>
      <header className="h-14 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-brand-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Layers className="h-5 w-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-base tracking-tight text-white flex items-center gap-2">
              DataFlow <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400 font-semibold border border-brand-500/30">Enterprise</span>
            </span>
          </div>

          <div className="h-5 w-[1px] bg-slate-800 mx-2" />

          {/* Workspace & Project Selector Display */}
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="bg-slate-800/80 px-2 py-1 rounded text-slate-300 font-medium border border-slate-700/50">
              {activeWorkspace?.name || 'Enterprise Workspace'}
            </span>
            <span>/</span>
            <span className="text-brand-400 font-medium">
              {activeProject?.name || 'Analytics Project'}
            </span>
          </div>

          <div className="h-5 w-[1px] bg-slate-800 mx-2" />

          {/* Git Source Control Widget */}
          {gitRepo?.is_connected ? (
            <div className="flex items-center gap-1.5 bg-slate-950/70 border border-slate-800 rounded-lg p-1 text-xs">
              {/* Branch selector dropdown pill */}
              <button
                onClick={() => setIsBranchModalOpen(true)}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 font-mono text-[11px] transition"
                title="Switch or create branch"
              >
                <GitBranch className="h-3.5 w-3.5 text-brand-400" />
                <span className="max-w-[120px] truncate">{gitRepo.current_branch}</span>
                <ChevronDown className="h-3 w-3 text-slate-500" />
              </button>

              {/* Pending Changes Badge */}
              <button
                onClick={() => setIsCommitModalOpen(true)}
                className={`px-2 py-0.5 rounded text-[11px] font-medium flex items-center gap-1 transition ${
                  (diffSummary?.total_changes || 0) > 0
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
                    : 'text-slate-400 hover:bg-slate-800/60'
                }`}
                title="Review local changes and commit"
              >
                {(diffSummary?.total_changes || 0) > 0 ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                    <span>{diffSummary?.total_changes} changed</span>
                  </>
                ) : (
                  <span className="text-slate-500">Up to date</span>
                )}
              </button>

              {/* Commit & Push Button */}
              <button
                onClick={() => setIsCommitModalOpen(true)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
                title="Commit & Push to Remote"
              >
                <UploadCloud className="h-3.5 w-3.5 text-brand-400" />
              </button>

              {/* Sync / Pull Button */}
              <button
                onClick={handlePullSync}
                disabled={isPulling}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition flex items-center gap-1"
                title="Pull from Remote"
              >
                <DownloadCloud className={`h-3.5 w-3.5 ${isPulling ? 'animate-bounce text-brand-400' : 'text-slate-400'}`} />
                {pullMessage && <span className="text-[10px] text-emerald-400">{pullMessage}</span>}
              </button>

              {/* Git Settings */}
              <button
                onClick={() => setIsSettingsModalOpen(true)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
                title="Git Repository Configuration"
              >
                <Settings className="h-3.5 w-3.5 text-slate-400" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-slate-700/60 font-mono">
                Live Mode
              </span>
              <button
                onClick={() => setIsSettingsModalOpen(true)}
                className="flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 font-medium px-2 py-1 rounded hover:bg-brand-500/10 transition border border-brand-500/20"
              >
                <FolderGit2 className="h-3.5 w-3.5" />
                <span>Connect Git</span>
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4 text-xs">
          {/* System Engine Status */}
          <div className="flex items-center gap-2 bg-emerald-500/10 text-emerald-400 px-2.5 py-1 rounded-full border border-emerald-500/20">
            <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-medium">Engine: Online</span>
          </div>

          <div className="flex items-center gap-2 bg-slate-800/70 text-slate-300 px-2.5 py-1 rounded border border-slate-700/50">
            <Cpu className="h-3.5 w-3.5 text-brand-400" />
            <span>Worker Pool: 4 Active</span>
          </div>

          <div className="flex items-center gap-2 border-l border-slate-800 pl-4">
            <div className="h-7 w-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300">
              A
            </div>
            <div className="hidden sm:block text-left">
              <div className="text-slate-200 font-medium">Admin</div>
              <div className="text-[10px] text-slate-500">Platform Engineer</div>
            </div>
          </div>
        </div>
      </header>

      {/* Modals */}
      {activeProject && (
        <>
          <GitCommitModal
            isOpen={isCommitModalOpen}
            onClose={() => setIsCommitModalOpen(false)}
            projectId={activeProject.id}
            currentBranch={gitRepo?.current_branch || 'main'}
            onSuccess={fetchGitStatus}
          />
          <GitSettingsModal
            isOpen={isSettingsModalOpen}
            onClose={() => setIsSettingsModalOpen(false)}
            projectId={activeProject.id}
            currentRepo={gitRepo}
            onSuccess={fetchGitStatus}
          />
          <GitBranchModal
            isOpen={isBranchModalOpen}
            onClose={() => setIsBranchModalOpen(false)}
            projectId={activeProject.id}
            currentBranch={gitRepo?.current_branch || 'main'}
            onSuccess={(newBranch) => {
              fetchGitStatus();
            }}
          />
        </>
      )}
    </>
  );
};
