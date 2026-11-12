import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import {
  X,
  Folder,
  FolderOpen,
  File,
  ChevronRight,
  RefreshCw,
  Search,
  HardDrive,
  Database,
  Check,
  FileCode,
  FileSpreadsheet,
  FileText,
  AlertCircle
} from 'lucide-react';

interface StorageItem {
  name: string;
  path: string;
  is_directory: boolean;
  size_in_bytes: number;
  last_modified?: string;
  content_type?: string;
}

interface StorageBrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectionId: string;
  connectionName?: string;
  initialContainer?: string;
  initialPath?: string;
  onSelect: (container: string, path: string, isDirectory: boolean) => void;
}

export const StorageHierarchyBrowserModal: React.FC<StorageBrowserModalProps> = ({
  isOpen,
  onClose,
  connectionId,
  connectionName,
  initialContainer = '',
  initialPath = '',
  onSelect
}) => {
  const [containers, setContainers] = useState<string[]>([]);
  const [selectedContainer, setSelectedContainer] = useState<string>(initialContainer);
  const [currentPrefix, setCurrentPrefix] = useState<string>('');
  const [directories, setDirectories] = useState<string[]>([]);
  const [files, setFiles] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState<string>('');
  const [selectedItem, setSelectedItem] = useState<{ path: string; isDir: boolean } | null>(null);

  // Load containers on open
  useEffect(() => {
    if (!isOpen || !connectionId) return;
    loadContainers();
  }, [isOpen, connectionId]);

  // Load items whenever selectedContainer or currentPrefix changes
  useEffect(() => {
    if (selectedContainer) {
      loadItems(selectedContainer, currentPrefix);
    }
  }, [selectedContainer, currentPrefix]);

  const loadContainers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/connections/${connectionId}/storage/containers`);
      const list = res.data.containers || [];
      setContainers(list);
      if (list.length > 0) {
        const nextContainer = initialContainer && list.includes(initialContainer) ? initialContainer : list[0];
        setSelectedContainer(nextContainer);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load storage containers.');
    } finally {
      setLoading(false);
    }
  };

  const loadItems = async (container: string, prefix: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/connections/${connectionId}/storage/items`, {
        params: {
          container,
          prefix: prefix || undefined,
          recursive: false,
          limit: 250
        }
      });
      setDirectories(res.data.directories || []);
      setFiles(res.data.files || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to list storage items.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const navigateToSubdir = (dirName: string) => {
    const newPrefix = currentPrefix ? `${currentPrefix.replace(/\/$/, '')}/${dirName}/` : `${dirName}/`;
    setCurrentPrefix(newPrefix);
    setSelectedItem(null);
  };

  const navigateToBreadcrumb = (index: number, segments: string[]) => {
    if (index === -1) {
      setCurrentPrefix('');
    } else {
      const target = segments.slice(0, index + 1).join('/') + '/';
      setCurrentPrefix(target);
    }
    setSelectedItem(null);
  };

  const breadcrumbs = currentPrefix ? currentPrefix.split('/').filter(Boolean) : [];

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getFileIcon = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.endsWith('.parquet') || lower.endsWith('.orc') || lower.endsWith('.avro')) {
      return <FileCode className="h-4 w-4 text-emerald-400 shrink-0" />;
    }
    if (lower.endsWith('.csv') || lower.endsWith('.tsv') || lower.endsWith('.xlsx')) {
      return <FileSpreadsheet className="h-4 w-4 text-blue-400 shrink-0" />;
    }
    if (lower.endsWith('.json') || lower.endsWith('.jsonl')) {
      return <FileCode className="h-4 w-4 text-amber-400 shrink-0" />;
    }
    return <FileText className="h-4 w-4 text-slate-400 shrink-0" />;
  };

  const filteredDirectories = directories.filter((d) =>
    d.toLowerCase().includes(filterQuery.toLowerCase())
  );
  const filteredFiles = files.filter((f) =>
    f.name.toLowerCase().includes(filterQuery.toLowerCase())
  );

  const handleConfirmSelect = () => {
    if (!selectedContainer) return;
    const path = selectedItem ? selectedItem.path : currentPrefix;
    const isDir = selectedItem ? selectedItem.isDir : true;
    onSelect(selectedContainer, path, isDir);
    onClose();
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 cursor-pointer"
      onClick={onClose}
    >
      <div 
        className="bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl w-full max-w-3xl flex flex-col h-[650px] overflow-hidden text-xs cursor-default"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400">
              <HardDrive className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Storage Hierarchy Browser</h2>
              <p className="text-[11px] text-slate-400">
                Browsing objects in <span className="text-brand-300 font-mono">{connectionName || 'Storage Connection'}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Toolbar: Container dropdown, Breadcrumbs & Search */}
        <div className="p-4 border-b border-slate-800 bg-slate-950/40 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-64">
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                Container / Bucket
              </label>
              <select
                value={selectedContainer}
                onChange={(e) => {
                  setSelectedContainer(e.target.value);
                  setCurrentPrefix('');
                  setSelectedItem(null);
                }}
                disabled={loading || containers.length === 0}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs font-medium focus:border-brand-500 focus:outline-none"
              >
                {containers.length === 0 && <option value="">No containers found</option>}
                {containers.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1">
              <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                Filter Items
              </label>
              <div className="relative">
                <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter files and directories..."
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 text-xs focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="pt-4">
              <button
                onClick={() => selectedContainer && loadItems(selectedContainer, currentPrefix)}
                disabled={loading}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Refresh"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Breadcrumb path */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] overflow-x-auto">
            <button
              onClick={() => navigateToBreadcrumb(-1, [])}
              className="text-brand-400 hover:text-brand-300 font-semibold flex items-center gap-1 shrink-0"
            >
              <Database className="h-3 w-3" />
              <span>{selectedContainer || 'root'}</span>
            </button>
            {breadcrumbs.map((segment, idx) => (
              <React.Fragment key={idx}>
                <ChevronRight className="h-3 w-3 text-slate-600 shrink-0" />
                <button
                  onClick={() => navigateToBreadcrumb(idx, breadcrumbs)}
                  className={`hover:text-white transition shrink-0 ${
                    idx === breadcrumbs.length - 1 ? 'text-white font-medium' : 'text-slate-400'
                  }`}
                >
                  {segment}
                </button>
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* File & Directory List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-1">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Failed to browse storage</p>
                <p className="text-[11px] text-rose-300">{error}</p>
              </div>
            </div>
          )}

          {loading && (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <RefreshCw className="h-6 w-6 animate-spin mx-auto text-brand-400" />
              <p>Scanning cloud storage objects...</p>
            </div>
          )}

          {!loading && !error && filteredDirectories.length === 0 && filteredFiles.length === 0 && (
            <div className="py-16 text-center text-slate-500 space-y-1">
              <FolderOpen className="h-8 w-8 mx-auto text-slate-600 stroke-1" />
              <p className="text-slate-400 font-medium">Directory is empty</p>
              <p className="text-[11px]">No matching files or subdirectories found under this prefix.</p>
            </div>
          )}

          {/* Directory entries */}
          {!loading &&
            filteredDirectories.map((dir) => {
              const fullDirPath = currentPrefix ? `${currentPrefix.replace(/\/$/, '')}/${dir}/` : `${dir}/`;
              const isSelected = selectedItem?.path === fullDirPath;
              return (
                <div
                  key={`dir-${dir}`}
                  onClick={() => setSelectedItem({ path: fullDirPath, isDir: true })}
                  onDoubleClick={() => navigateToSubdir(dir)}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition select-none ${
                    isSelected
                      ? 'bg-brand-600/20 border border-brand-500/40 text-brand-200'
                      : 'hover:bg-slate-800/60 text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Folder className="h-4 w-4 text-amber-400 shrink-0" />
                    <span className="font-medium truncate">{dir}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigateToSubdir(dir);
                      }}
                      className="px-2 py-0.5 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                    >
                      Open
                    </button>
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider">Directory</span>
                  </div>
                </div>
              );
            })}

          {/* File entries */}
          {!loading &&
            filteredFiles.map((file) => {
              const isSelected = selectedItem?.path === file.path;
              return (
                <div
                  key={`file-${file.path}`}
                  onClick={() => setSelectedItem({ path: file.path, isDir: false })}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition select-none ${
                    isSelected
                      ? 'bg-brand-600/25 border border-brand-500/50 text-white shadow-sm'
                      : 'hover:bg-slate-800/50 text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {getFileIcon(file.name)}
                    <span className="truncate">{file.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-[11px] text-slate-400 shrink-0">
                    <span>{formatBytes(file.size_in_bytes)}</span>
                    {file.last_modified && (
                      <span className="text-slate-500">
                        {new Date(file.last_modified).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
        </div>

        {/* Footer with Selection Details and Actions */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <div className="min-w-0 flex-1 mr-4">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Selected Target</span>
            <div className="text-slate-300 font-mono text-[11px] truncate">
              {selectedContainer ? (
                <>
                  <span className="text-brand-400">{selectedContainer}</span>
                  <span className="text-slate-500">/</span>
                  <span>{selectedItem ? selectedItem.path : currentPrefix || '(root directory)'}</span>
                </>
              ) : (
                <span className="text-slate-500">No container selected</span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmSelect}
              disabled={!selectedContainer}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold transition disabled:opacity-50 shadow-md shadow-brand-600/20"
            >
              <Check className="h-3.5 w-3.5" />
              <span>Select Path</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
