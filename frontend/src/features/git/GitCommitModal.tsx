import React, { useState, useEffect } from 'react';
import { 
  X, 
  GitCommit, 
  GitPullRequest, 
  UploadCloud, 
  FileCode, 
  Plus, 
  Edit3, 
  Trash2, 
  CheckCircle2, 
  AlertCircle,
  Eye,
  RefreshCw
} from 'lucide-react';
import api from '../../api/client';

interface GitFileDiff {
  path: string;
  asset_type: string;
  asset_name: string;
  status: 'added' | 'modified' | 'deleted' | 'unchanged';
  old_content?: string;
  new_content?: string;
}

interface GitDiffResponse {
  branch: string;
  total_changes: number;
  files: GitFileDiff[];
}

interface GitCommitModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  currentBranch: string;
  onSuccess: () => void;
}

export const GitCommitModal: React.FC<GitCommitModalProps> = ({
  isOpen,
  onClose,
  projectId,
  currentBranch,
  onSuccess
}) => {
  const [diffData, setDiffData] = useState<GitDiffResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<GitFileDiff | null>(null);
  const [commitMessage, setCommitMessage] = useState('');
  const [authorName, setAuthorName] = useState('DataForge Developer');
  const [authorEmail, setAuthorEmail] = useState('dev@dataforge.internal');
  const [isLoading, setIsLoading] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && projectId) {
      loadDiff();
    }
  }, [isOpen, projectId]);

  const loadDiff = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.get<GitDiffResponse>(`/git/diff?project_id=${projectId}`);
      setDiffData(res.data);
      if (res.data.files.length > 0) {
        setSelectedFile(res.data.files[0]);
      } else {
        setSelectedFile(null);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to inspect git differences');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCommitAndPush = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commitMessage.trim()) {
      setError('Commit message is required');
      return;
    }

    try {
      setIsCommitting(true);
      setError(null);
      await api.post(`/git/commit?project_id=${projectId}`, {
        branch: currentBranch,
        message: commitMessage.trim(),
        author_name: authorName,
        author_email: authorEmail
      });
      setSuccessMessage('Successfully committed and pushed changes to remote!');
      setTimeout(() => {
        setSuccessMessage(null);
        setCommitMessage('');
        onSuccess();
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Commit and push failed');
    } finally {
      setIsCommitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-5xl w-full shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-500/20 text-brand-400 border border-brand-500/30">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                Commit & Push Changes
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
                  {currentBranch}
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Review canonical JSON asset differences and commit to remote repository
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

        {/* Content Body */}
        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {/* Left: Changed Files List */}
          <div className="w-full md:w-80 border-r border-slate-800 flex flex-col bg-slate-950/40">
            <div className="p-3 border-b border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium uppercase tracking-wider text-[11px]">
                Pending Changes ({diffData?.total_changes || 0})
              </span>
              <button 
                onClick={loadDiff}
                disabled={isLoading}
                className="text-slate-400 hover:text-slate-200 transition p-1 hover:bg-slate-800 rounded"
                title="Refresh Diff"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {isLoading ? (
                <div className="py-8 text-center text-xs text-slate-500">
                  <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-2 text-slate-400" />
                  Calculating workspace tree diff...
                </div>
              ) : diffData?.files && diffData.files.length > 0 ? (
                diffData.files.map((file) => {
                  const isSelected = selectedFile?.path === file.path;
                  return (
                    <button
                      key={file.path}
                      onClick={() => setSelectedFile(file)}
                      className={`w-full text-left p-2.5 rounded-lg text-xs transition flex items-center justify-between group ${
                        isSelected 
                          ? 'bg-brand-600/20 border border-brand-500/40 text-brand-300' 
                          : 'hover:bg-slate-800/50 text-slate-300 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {file.status === 'added' && <Plus className="h-3.5 w-3.5 text-emerald-400 shrink-0" />}
                        {file.status === 'modified' && <Edit3 className="h-3.5 w-3.5 text-amber-400 shrink-0" />}
                        {file.status === 'deleted' && <Trash2 className="h-3.5 w-3.5 text-rose-400 shrink-0" />}
                        <div className="truncate">
                          <div className="font-medium truncate">{file.asset_name}</div>
                          <div className="text-[10px] text-slate-500 font-mono truncate">{file.path}</div>
                        </div>
                      </div>
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded shrink-0 ${
                        file.status === 'added' 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : file.status === 'modified'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}>
                        {file.status}
                      </span>
                    </button>
                  );
                })
              ) : (
                <div className="py-12 text-center text-xs text-slate-500 px-4">
                  <CheckCircle2 className="h-6 w-6 text-emerald-400 mx-auto mb-2" />
                  Workspace is completely clean and up-to-date with Git.
                </div>
              )}
            </div>
          </div>

          {/* Right: File Diff Inspector & Commit Form */}
          <div className="flex-1 flex flex-col overflow-hidden bg-slate-900/40">
            {/* Diff Preview */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs">
              {selectedFile ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2">
                    <span className="text-white font-medium flex items-center gap-2">
                      <FileCode className="h-4 w-4 text-brand-400" />
                      {selectedFile.path}
                    </span>
                    <span className="text-slate-500 text-[11px]">Canonical Asset Model</span>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-[11px]">
                    {selectedFile.status !== 'added' && (
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 overflow-x-auto max-h-72">
                        <div className="text-rose-400 text-[10px] font-sans font-semibold mb-2 flex items-center gap-1">
                          <Trash2 className="h-3 w-3" /> Base Remote Version
                        </div>
                        <pre className="text-slate-400 whitespace-pre font-mono">
                          {selectedFile.old_content || '/* Empty */'}
                        </pre>
                      </div>
                    )}
                    {selectedFile.status !== 'deleted' && (
                      <div className={`bg-slate-950 p-3 rounded-lg border border-slate-800/80 overflow-x-auto max-h-72 ${
                        selectedFile.status === 'added' ? 'lg:col-span-2' : ''
                      }`}>
                        <div className="text-emerald-400 text-[10px] font-sans font-semibold mb-2 flex items-center gap-1">
                          <Plus className="h-3 w-3" /> New Local Workspace Version
                        </div>
                        <pre className="text-emerald-300 whitespace-pre font-mono">
                          {selectedFile.new_content || '/* Empty */'}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                  Select a file on the left to preview canonical differences
                </div>
              )}
            </div>

            {/* Commit Form Footer */}
            <form onSubmit={handleCommitAndPush} className="p-4 border-t border-slate-800 bg-slate-900/90 space-y-3">
              {error && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {successMessage && (
                <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{successMessage}</span>
                </div>
              )}

              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-300">
                  Commit Message <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Update customer bronze ingestion pipeline and triggers"
                  value={commitMessage}
                  onChange={(e) => setCommitMessage(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-sans"
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-2 text-slate-400 text-xs">
                  <span className="text-slate-500">Author:</span>
                  <span className="text-slate-300 font-mono text-[11px]">{authorName}</span>
                </div>

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
                    disabled={isCommitting || !diffData?.total_changes || !commitMessage.trim()}
                    className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-lg shadow-brand-600/30 flex items-center gap-2 transition"
                  >
                    {isCommitting ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        Pushing to Git...
                      </>
                    ) : (
                      <>
                        <UploadCloud className="h-3.5 w-3.5" />
                        Commit & Push
                      </>
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
