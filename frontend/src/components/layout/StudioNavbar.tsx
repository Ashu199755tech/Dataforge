import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAppStore, EnvironmentType } from '../../store/useAppStore';
import { 
  Search,
  Bell, 
  HelpCircle, 
  Settings, 
  ChevronDown, 
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  GitBranch, 
  FolderGit2, 
  UploadCloud, 
  DownloadCloud, 
  Cpu, 
  CheckCircle2, 
  AlertTriangle,
  Building2,
  ExternalLink,
  BookOpen,
  Keyboard,
  LogOut,
  Layers,
  Sparkles,
  Zap,
  ShieldCheck,
  Server
} from 'lucide-react';
import api from '../../api/client';
import { GitCommitModal } from '../../features/git/GitCommitModal';
import { GitSettingsModal } from '../../features/git/GitSettingsModal';
import { GitBranchModal } from '../../features/git/GitBranchModal';
import { GlobalSearchModal } from '../common/GlobalSearchModal';

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

const TAB_LABELS: Record<string, string> = {
  dashboard: 'Home',
  pipelines: 'Data Pipelines',
  designer: 'Pipeline Designer',
  dataflows: 'Data Flows',
  connections: 'Connections',
  datasets: 'Datasets',
  triggers: 'Triggers',
  runs: 'Pipeline Runs',
  observability: 'Fleet & Alerts',
  runtimes: 'Runtime Manager',
  deployments: 'Deployments & CI/CD',
  lineage: 'Data Lineage',
  dq: 'Data Quality',
  billing: 'Billing & Costs'
};

export const StudioNavbar: React.FC = () => {
  const { 
    currentTab,
    workspaces, 
    activeWorkspace, 
    setActiveWorkspace,
    projects,
    activeProject, 
    setActiveProject,
    selectedEnvironment, 
    setSelectedEnvironment,
    setCurrentTab
  } = useAppStore();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [gitRepo, setGitRepo] = useState<GitRepositoryResponse | null>(null);
  const [diffSummary, setDiffSummary] = useState<GitDiffSummary | null>(null);
  const [isPulling, setIsPulling] = useState(false);
  const [pullMessage, setPullMessage] = useState<string | null>(null);

  // Dropdown states
  const [isWorkspaceDropdownOpen, setIsWorkspaceDropdownOpen] = useState(false);
  const [isEnvDropdownOpen, setIsEnvDropdownOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState<any[]>([]);

  // Git Modals state
  const [isCommitModalOpen, setIsCommitModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isBranchModalOpen, setIsBranchModalOpen] = useState(false);

  const headerRef = useRef<HTMLElement>(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (headerRef.current && !headerRef.current.contains(e.target as Node)) {
        setIsWorkspaceDropdownOpen(false);
        setIsEnvDropdownOpen(false);
        setIsUserMenuOpen(false);
        setIsHelpOpen(false);
        setIsNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Global Ctrl+K / Cmd+K shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const fetchGitStatus = useCallback(async () => {
    if (!activeProject?.id) return;
    try {
      const res = await api.get<GitRepositoryResponse>(`/git/status?project_id=${activeProject.id}`);
      setGitRepo(res.data);
      if (res.data.is_connected) {
        try {
          const diffRes = await api.get<GitDiffSummary>(`/git/diff?project_id=${activeProject.id}`);
          setDiffSummary({
            branch: diffRes.data.branch,
            total_changes: diffRes.data.total_changes
          });
        } catch {
          setDiffSummary(null);
        }
      } else {
        setDiffSummary(null);
      }
    } catch {
      setGitRepo(null);
      setDiffSummary(null);
    }
  }, [activeProject?.id]);

  useEffect(() => {
    fetchGitStatus();
  }, [fetchGitStatus]);

  // Load recent notifications
  useEffect(() => {
    const loadAlerts = async () => {
      try {
        const res = await api.get('/runs?limit=5&status=Failed');
        if (Array.isArray(res.data)) {
          setUnreadNotifications(res.data.slice(0, 3));
        }
      } catch {}
    };
    loadAlerts();
  }, []);

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

  const getEnvBadgeColor = (env: EnvironmentType) => {
    switch (env) {
      case 'Development': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      case 'Testing': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'Staging': return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
      case 'Production': return 'text-rose-400 bg-rose-500/10 border-rose-500/30';
    }
  };

  return (
    <>
      <header ref={headerRef} className="h-[50px] border-b border-slate-800 bg-slate-900/95 backdrop-blur-md px-3.5 flex items-center justify-between sticky top-0 z-40 select-none">
        
        {/* ================= LEFT SECTION: BRAND, WORKSPACE & ENV ================= */}
        <div className="flex items-center gap-2.5">
          {/* Original DataForge Logo Mark */}
          <div 
            onClick={() => setCurrentTab('dashboard')}
            className="flex items-center gap-2.5 cursor-pointer hover:opacity-90 transition"
            title="Go to Home Workspace"
          >
            <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-brand-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-md shadow-brand-500/20 border border-brand-400/30">
              <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 14.5L12 3l8 11.5-8 6.5-8-6.5z" />
                <path d="M12 3v18" />
              </svg>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-sm tracking-tight text-white">
                DataForge
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded font-semibold bg-brand-500/15 text-brand-400 border border-brand-500/25 tracking-wide">
                STUDIO
              </span>
            </div>
          </div>

          {/* In-app Browser History Controls */}
          <div className="flex items-center gap-0.5 bg-slate-950/70 p-0.5 rounded-md border border-slate-800">
            <button
              onClick={() => {
                if (window.history.length > 1) {
                  window.history.back();
                } else {
                  setCurrentTab('dashboard');
                }
              }}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Go Back (Alt + Left Arrow)"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => window.history.forward()}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Go Forward (Alt + Right Arrow)"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="h-4 w-[1px] bg-slate-800 mx-0.5 hidden sm:block" />

          {/* Workspace Switcher Dropdown */}
          <div className="relative">
            <button
              onClick={() => {
                setIsWorkspaceDropdownOpen(!isWorkspaceDropdownOpen);
                setIsEnvDropdownOpen(false);
              }}
              className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800/70 border border-transparent hover:border-slate-700/60 transition"
              title="Switch Workspace"
            >
              <Building2 className="h-3.5 w-3.5 text-slate-400" />
              <span className="max-w-[130px] truncate">{activeWorkspace?.name || 'Default Workspace'}</span>
              <ChevronDown className="h-3 w-3 text-slate-500" />
            </button>

            {isWorkspaceDropdownOpen && (
              <div className="absolute left-0 top-full mt-1.5 w-56 bg-slate-900 border border-slate-700/80 rounded-lg shadow-xl z-50 p-1 divide-y divide-slate-800/60">
                <div className="px-2 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  Workspaces
                </div>
                <div className="py-1 space-y-0.5">
                  {workspaces.map(ws => (
                    <button
                      key={ws.id}
                      onClick={() => {
                        setActiveWorkspace(ws);
                        setIsWorkspaceDropdownOpen(false);
                      }}
                      className={`w-full text-left px-2 py-1.5 rounded text-xs flex items-center justify-between ${
                        activeWorkspace?.id === ws.id 
                          ? 'bg-brand-600/20 text-brand-300 font-medium' 
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <span className="truncate">{ws.name}</span>
                      {activeWorkspace?.id === ws.id && <CheckCircle2 className="h-3.5 w-3.5 text-brand-400 shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <span className="text-slate-600 text-xs">/</span>

          {/* Environment Selector Dropdown */}
          <div className="relative">
            <button
              onClick={() => {
                setIsEnvDropdownOpen(!isEnvDropdownOpen);
                setIsWorkspaceDropdownOpen(false);
              }}
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border transition ${getEnvBadgeColor(selectedEnvironment)}`}
              title="Target Environment"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
              <span>{selectedEnvironment}</span>
              <ChevronDown className="h-2.5 w-2.5 opacity-70" />
            </button>

            {isEnvDropdownOpen && (
              <div className="absolute left-0 top-full mt-1.5 w-44 bg-slate-900 border border-slate-700/80 rounded-lg shadow-xl z-50 p-1 divide-y divide-slate-800/60">
                <div className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  Select Environment
                </div>
                <div className="py-1 space-y-0.5">
                  {(['Development', 'Testing', 'Staging', 'Production'] as EnvironmentType[]).map(env => (
                    <button
                      key={env}
                      onClick={() => {
                        setSelectedEnvironment(env);
                        setIsEnvDropdownOpen(false);
                      }}
                      className={`w-full text-left px-2 py-1.5 rounded text-xs flex items-center justify-between ${
                        selectedEnvironment === env 
                          ? 'bg-brand-600/20 text-brand-300 font-medium' 
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className={`h-1.5 w-1.5 rounded-full ${
                          env === 'Development' ? 'bg-emerald-400' :
                          env === 'Testing' ? 'bg-amber-400' :
                          env === 'Staging' ? 'bg-purple-400' : 'bg-rose-400'
                        }`} />
                        {env}
                      </span>
                      {selectedEnvironment === env && <CheckCircle2 className="h-3 w-3 text-brand-400" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Active Page Breadcrumb */}
          {currentTab !== 'dashboard' && (
            <div className="hidden lg:flex items-center gap-1.5 text-xs text-slate-400 pl-0.5">
              <span className="text-slate-600">/</span>
              <span className="text-slate-200 font-medium">{TAB_LABELS[currentTab] || currentTab}</span>
            </div>
          )}
        </div>

        {/* ================= CENTER SECTION: GLOBAL SEARCH ================= */}
        <div className="hidden md:flex items-center justify-center flex-1 max-w-md mx-4">
          <button
            onClick={() => setIsSearchOpen(true)}
            className="w-full h-8 px-3 rounded-lg bg-slate-950/70 border border-slate-800 hover:border-slate-700 text-slate-400 text-xs flex items-center justify-between transition group shadow-inner"
          >
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-slate-500 group-hover:text-brand-400 transition" />
              <span className="text-slate-400 group-hover:text-slate-200">
                Search pipelines, datasets, connections, triggers...
              </span>
            </div>
            <kbd className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800/80 border border-slate-700/60 text-slate-400 font-mono">
              Ctrl+K
            </kbd>
          </button>
        </div>

        {/* ================= RIGHT SECTION: GIT, STATUS, USER ================= */}
        <div className="flex items-center gap-2 text-xs">
          {/* Git Source Control Widget */}
          {gitRepo?.is_connected ? (
            <div className="flex items-center gap-1 bg-slate-950/80 border border-slate-800 rounded-lg p-0.5 text-xs">
              <button
                onClick={() => setIsBranchModalOpen(true)}
                className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 font-mono text-[11px] transition"
                title="Active branch"
              >
                <GitBranch className="h-3 w-3 text-brand-400" />
                <span className="max-w-[90px] truncate">{gitRepo.current_branch}</span>
                <ChevronDown className="h-2.5 w-2.5 text-slate-500" />
              </button>

              <button
                onClick={() => setIsCommitModalOpen(true)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 transition ${
                  (diffSummary?.total_changes || 0) > 0
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : 'text-slate-400 hover:bg-slate-800'
                }`}
                title="Commit changes"
              >
                {(diffSummary?.total_changes || 0) > 0 ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                    <span>{diffSummary?.total_changes}</span>
                  </>
                ) : (
                  <span>Synced</span>
                )}
              </button>

              <button
                onClick={handlePullSync}
                disabled={isPulling}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
                title="Pull from remote"
              >
                <DownloadCloud className={`h-3 w-3 ${isPulling ? 'animate-bounce text-brand-400' : 'text-slate-400'}`} />
              </button>

              <button
                onClick={() => setIsSettingsModalOpen(true)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
                title="Git Repository Configuration"
              >
                <Settings className="h-3 w-3 text-slate-400" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsSettingsModalOpen(true)}
              className="flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 font-medium px-2 py-1 rounded hover:bg-brand-500/10 transition border border-brand-500/20"
              title="Connect GitHub or remote repository"
            >
              <FolderGit2 className="h-3 w-3" />
              <span>Connect Git</span>
            </button>
          )}

          {/* Engine Status Badge */}
          <div className="hidden sm:flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/20 text-[11px]">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-medium">Online</span>
          </div>

          {/* Notifications Center */}
          <div className="relative">
            <button
              onClick={() => {
                setIsNotificationsOpen(!isNotificationsOpen);
                setIsUserMenuOpen(false);
                setIsHelpOpen(false);
              }}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 relative transition"
              title="Notifications"
            >
              <Bell className="h-4 w-4" />
              {unreadNotifications.length > 0 && (
                <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
              )}
            </button>

            {isNotificationsOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-72 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl z-50 p-2 divide-y divide-slate-800/60">
                <div className="px-2 py-1.5 text-xs font-semibold text-white flex items-center justify-between">
                  <span>Notifications</span>
                  <span className="text-[10px] text-slate-400">{unreadNotifications.length} recent</span>
                </div>
                <div className="py-1 divide-y divide-slate-800/40">
                  {unreadNotifications.length === 0 ? (
                    <div className="p-3 text-center text-xs text-slate-500">
                      No critical alerts or failures.
                    </div>
                  ) : (
                    unreadNotifications.map((notif: any) => (
                      <div 
                        key={notif.id} 
                        onClick={() => {
                          setCurrentTab('runs');
                          setIsNotificationsOpen(false);
                        }}
                        className="p-2 text-xs hover:bg-slate-800/60 rounded cursor-pointer transition"
                      >
                        <div className="font-medium text-rose-300 flex items-center gap-1.5">
                          <AlertTriangle className="h-3 w-3 text-rose-400 shrink-0" />
                          <span className="truncate">Pipeline Failure: {notif.pipeline_id.substring(0, 8)}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {new Date(notif.started_at).toLocaleTimeString()}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Documentation / Help */}
          <div className="relative">
            <button
              onClick={() => {
                setIsHelpOpen(!isHelpOpen);
                setIsUserMenuOpen(false);
                setIsNotificationsOpen(false);
              }}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Help & Documentation"
            >
              <HelpCircle className="h-4 w-4" />
            </button>

            {isHelpOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-60 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl z-50 p-2 text-xs divide-y divide-slate-800/60">
                <div className="px-2 py-1.5 font-semibold text-white">
                  DataForge Studio Guide
                </div>
                <div className="py-1 space-y-1">
                  <a 
                    href="https://github.com" 
                    target="_blank" 
                    rel="noreferrer"
                    className="flex items-center justify-between px-2 py-1.5 rounded text-slate-300 hover:bg-slate-800"
                  >
                    <span className="flex items-center gap-2"><BookOpen className="h-3.5 w-3.5 text-brand-400" /> API Reference</span>
                    <ExternalLink className="h-3 w-3 text-slate-500" />
                  </a>
                  <button 
                    onClick={() => {
                      setIsHelpOpen(false);
                      setIsSearchOpen(true);
                    }}
                    className="w-full flex items-center justify-between px-2 py-1.5 rounded text-slate-300 hover:bg-slate-800 text-left"
                  >
                    <span className="flex items-center gap-2"><Keyboard className="h-3.5 w-3.5 text-brand-400" /> Keyboard Shortcuts</span>
                    <span className="font-mono text-[10px] text-slate-500">Ctrl+K</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="h-4 w-[1px] bg-slate-800 mx-1" />

          {/* User Profile Dropdown */}
          <div className="relative">
            <button
              onClick={() => {
                setIsUserMenuOpen(!isUserMenuOpen);
                setIsHelpOpen(false);
                setIsNotificationsOpen(false);
              }}
              className="flex items-center gap-2 p-1 rounded-lg hover:bg-slate-800 transition"
            >
              <div className="h-7 w-7 rounded-full bg-gradient-to-tr from-brand-600 to-indigo-600 border border-slate-700 flex items-center justify-center font-bold text-white text-xs shadow-sm">
                A
              </div>
              <div className="hidden lg:block text-left text-xs leading-none">
                <div className="text-slate-200 font-medium">Admin</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Platform Engineer</div>
              </div>
              <ChevronDown className="h-3 w-3 text-slate-500 hidden sm:block" />
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-56 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl z-50 p-2 text-xs divide-y divide-slate-800/60">
                <div className="px-2 py-2">
                  <div className="font-medium text-white">Administrator</div>
                  <div className="text-[11px] text-slate-400 truncate">admin@dataforge.internal</div>
                  <div className="mt-1 text-[10px] px-1.5 py-0.5 rounded bg-brand-500/15 text-brand-300 inline-block font-mono">
                    Owner Role
                  </div>
                </div>
                <div className="py-1">
                  <div className="px-2 py-1 text-slate-400 hover:bg-slate-800 rounded cursor-pointer">
                    Workspace Preferences
                  </div>
                  <div className="px-2 py-1 text-slate-400 hover:bg-slate-800 rounded cursor-pointer">
                    API Access Tokens
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Search Modal */}
      <GlobalSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
      />

      {/* Git Modals */}
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
            onSuccess={() => fetchGitStatus()}
          />
        </>
      )}
    </>
  );
};
