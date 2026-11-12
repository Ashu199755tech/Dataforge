import React, { useState, useEffect } from 'react';
import { useAppStore } from '../../store/useAppStore';
import api from '../../api/client';
import { ListFilterSortBar } from '../../components/common/ListFilterSortBar';
import { 
  Plus, 
  Workflow, 
  Trash2, 
  ArrowRight, 
  Clock, 
  Layers, 
  Search, 
  Database,
  Table,
  Play,
  ArrowLeft
} from 'lucide-react';
import { DataFlowCanvas } from './DataFlowCanvas';

export const DataFlowsListPage: React.FC = () => {
  const { activeProject } = useAppStore();
  const [dataflows, setDataflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDfId, setSelectedDfId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDfName, setNewDfName] = useState('');
  const [newDfDesc, setNewDfDesc] = useState('');

  // Search & Sort state (Default: Newest First)
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<string>('newest');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const loadDataflows = async () => {
    if (!activeProject) return;
    setLoading(true);
    try {
      const res = await api.get(`/dataflows?project_id=${activeProject.id}`);
      setDataflows(res.data);
    } catch (err) {
      console.error('Failed to load dataflows:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDataflows();
  }, [activeProject]);

  const handleCreate = async () => {
    if (!activeProject || !newDfName.trim()) return;
    try {
      const res = await api.post('/dataflows', {
        project_id: activeProject.id,
        name: newDfName.trim(),
        description: newDfDesc.trim() || undefined
      });
      setShowCreateModal(false);
      setNewDfName('');
      setNewDfDesc('');
      setSelectedDfId(res.data.id);
    } catch (err) {
      console.error('Failed to create dataflow:', err);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Delete this Data Flow?')) return;
    try {
      await api.delete(`/dataflows/${id}`);
      setDataflows((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      console.error('Failed to delete dataflow:', err);
    }
  };

  if (selectedDfId) {
    return (
      <DataFlowCanvas
        dataflowId={selectedDfId}
        onBack={() => {
          setSelectedDfId(null);
          loadDataflows();
        }}
      />
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (window.history.length > 1) {
                window.history.back();
              } else {
                useAppStore.getState().setCurrentTab('dashboard');
              }
            }}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition shadow-sm flex items-center justify-center group"
            title="Go back (Alt + Left Arrow)"
          >
            <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Workflow className="h-6 w-6 text-brand-400" />
              <span>Visual Data Flows (ETL)</span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Build graphical data transformation graphs compiled to high-speed vectorized Polars and Spark execution.
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md shadow-brand-500/20 transition"
        >
          <Plus className="h-4 w-4" />
          <span>New Data Flow</span>
        </button>
      </div>

      {/* Search & Sort Bar */}
      {(() => {
        const filteredDataflows = dataflows.filter((df) => {
          if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            const matchName = (df.name || '').toLowerCase().includes(q);
            const matchDesc = (df.description || '').toLowerCase().includes(q);
            return matchName || matchDesc;
          }
          return true;
        });

        const sortedDataflows = [...filteredDataflows].sort((a, b) => {
          if (sortBy === 'newest') {
            const dateA = new Date(a.created_at || a.updated_at || 0).getTime();
            const dateB = new Date(b.created_at || b.updated_at || 0).getTime();
            return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
          }
          if (sortBy === 'oldest') {
            const dateA = new Date(a.created_at || a.updated_at || 0).getTime();
            const dateB = new Date(b.created_at || b.updated_at || 0).getTime();
            return sortDirection === 'asc' ? dateB - dateA : dateA - dateB;
          }
          if (sortBy === 'name_asc') {
            const cmp = (a.name || '').localeCompare(b.name || '');
            return sortDirection === 'asc' ? cmp : -cmp;
          }
          if (sortBy === 'name_desc') {
            const cmp = (b.name || '').localeCompare(a.name || '');
            return sortDirection === 'asc' ? cmp : -cmp;
          }
          return 0;
        });

        return (
          <>
            <ListFilterSortBar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search data flows by name, description..."
              currentSort={sortBy}
              onSortChange={setSortBy}
              sortDirection={sortDirection}
              onToggleDirection={() => setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
              sortOptions={[
                { id: 'newest', label: 'Newest First' },
                { id: 'oldest', label: 'Oldest First' },
                { id: 'name_asc', label: 'Name (A to Z)' },
                { id: 'name_desc', label: 'Name (Z to A)' }
              ]}
              totalCount={dataflows.length}
              filteredCount={sortedDataflows.length}
            />

            {/* Grid of Data Flows */}
            {loading ? (
              <div className="p-12 text-center text-slate-500 text-xs">
                Loading Data Flows...
              </div>
            ) : sortedDataflows.length === 0 ? (
              <div className="p-16 text-center bg-slate-900/40 border border-slate-800 rounded-xl space-y-3">
                <Workflow className="h-10 w-10 text-slate-600 mx-auto" />
                <h3 className="text-sm font-semibold text-slate-300">
                  {searchQuery ? 'No Data Flows Match Search' : 'No Data Flows in Project'}
                </h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  {searchQuery ? 'Try clearing your query.' : 'Create visual mapping data flows to clean, filter, join, aggregate, and reshape records between sources and sinks.'}
                </p>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition"
                >
                  Create Your First Data Flow
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sortedDataflows.map((df) => (
                  <div
                    key={df.id}
                    onClick={() => setSelectedDfId(df.id)}
                    className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 hover:border-brand-500/50 hover:bg-slate-900 transition cursor-pointer group flex flex-col justify-between space-y-3"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                          {df.node_count} Operators
                        </span>
                        <button
                          onClick={(e) => handleDelete(df.id, e)}
                          className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition"
                          title="Delete Data Flow"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <h3 className="font-semibold text-sm text-slate-200 group-hover:text-brand-300 transition mt-2">
                        {df.name}
                      </h3>
                      {df.description && (
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                          {df.description}
                        </p>
                      )}
                    </div>

                    <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
                      <span>{df.created_at ? new Date(df.created_at).toLocaleDateString() : 'Draft'}</span>
                      <span className="flex items-center gap-1 text-brand-400 group-hover:translate-x-0.5 transition font-medium">
                        Open Graph <ArrowRight className="h-3 w-3" />
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        );
      })()}

      {/* Modal: Create Data Flow */}
      {showCreateModal && (
        <div 
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setShowCreateModal(false)}
        >
          <div 
            className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-5 space-y-4 shadow-2xl cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <h3 className="text-sm font-bold text-slate-100">Create New Data Flow</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Design visual transformations for high-throughput data processing.
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Data Flow Name</label>
                <input
                  type="text"
                  placeholder="e.g. Sales_Cleanse_And_Aggregate"
                  value={newDfName}
                  onChange={(e) => setNewDfName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-200 font-medium"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Description (Optional)</label>
                <textarea
                  rows={2}
                  placeholder="Briefly describe the transformations..."
                  value={newDfDesc}
                  onChange={(e) => setNewDfDesc(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-200"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-3 py-1.5 rounded-lg text-slate-400 hover:text-slate-200 text-xs transition"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newDfName.trim()}
                className="px-4 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md transition disabled:opacity-50"
              >
                Create & Design
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
