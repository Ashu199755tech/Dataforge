import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Connection } from '../types';
import api from '../api/client';
import { 
  Database, 
  Plus, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  RefreshCw, 
  Server, 
  Eye, 
  Trash2,
  Table
} from 'lucide-react';

export const ConnectionsPage: React.FC = () => {
  const { connections, activeProject, fetchConnections } = useAppStore();
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string; latency?: number } | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedTables, setSelectedTables] = useState<any[] | null>(null);
  const [exploringConnName, setExploringConnName] = useState<string>('');

  // Form state
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('postgres');
  const [formHost, setFormHost] = useState('localhost');
  const [formPort, setFormPort] = useState('5432');
  const [formUser, setFormUser] = useState('postgres');
  const [formPassword, setFormPassword] = useState('');
  const [formDatabase, setFormDatabase] = useState('postgres');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchConnections();
  }, [activeProject]);

  const handleTestConnection = async (connId: string) => {
    setTestingId(connId);
    setTestResult(null);
    try {
      const res = await api.post(`/connections/${connId}/test`);
      setTestResult({
        id: connId,
        success: res.data.success,
        message: res.data.message,
        latency: res.data.latency_ms
      });
      fetchConnections();
    } catch (err: any) {
      setTestResult({
        id: connId,
        success: false,
        message: err.response?.data?.detail || 'Connection test failed'
      });
    } finally {
      setTestingId(null);
    }
  };

  const handleExploreTables = async (conn: Connection) => {
    setExploringConnName(conn.name);
    try {
      const res = await api.get(`/connections/${conn.id}/tables`);
      setSelectedTables(res.data.tables);
    } catch (err: any) {
      alert(`Failed to discover schema: ${err.message}`);
    }
  };

  const handleCreateConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    setIsSaving(true);
    try {
      await api.post('/connections', {
        project_id: activeProject.id,
        name: formName,
        connector_type: formType,
        config: {
          host: formHost,
          port: parseInt(formPort),
          user: formUser,
          password: formPassword,
          database: formDatabase
        }
      });
      setShowAddModal(false);
      setFormName('');
      setFormPassword('');
      fetchConnections();
    } catch (err: any) {
      alert(`Error creating connection: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Enterprise Connections</h1>
          <p className="text-xs text-slate-400">Secure credential vault and live schema connectors for data sources and analytical targets</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-sm"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Connection</span>
        </button>
      </div>

      {/* Connections List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {connections.map((conn) => (
          <div 
            key={conn.id} 
            className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition space-y-4 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className={`p-2 rounded-lg border ${
                    conn.connector_type === 'postgres' 
                      ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                      : conn.connector_type === 'mysql'
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  }`}>
                    <Database className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{conn.name}</h3>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                      {conn.connector_type}
                    </div>
                  </div>
                </div>

                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                  conn.status === 'Active'
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : conn.status === 'Failed'
                    ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    : 'bg-slate-700/30 text-slate-400 border-slate-700/50'
                }`}>
                  {conn.status === 'Active' && <CheckCircle2 className="h-2.5 w-2.5" />}
                  {conn.status === 'Failed' && <XCircle className="h-2.5 w-2.5" />}
                  {conn.status === 'Unverified' && <AlertCircle className="h-2.5 w-2.5" />}
                  {conn.status}
                </span>
              </div>

              {conn.description && (
                <p className="mt-2 text-xs text-slate-400 line-clamp-2">{conn.description}</p>
              )}

              {/* Endpoint Details */}
              <div className="mt-3 p-2 rounded bg-slate-950/60 border border-slate-800/80 text-[11px] font-mono text-slate-400 space-y-0.5">
                <div>Host: <span className="text-slate-300">{conn.config_masked.host || 'local'}</span>:{conn.config_masked.port || ''}</div>
                <div>Database: <span className="text-slate-300">{conn.config_masked.database}</span></div>
                <div>User: <span className="text-slate-300">{conn.config_masked.user}</span></div>
              </div>

              {/* Live Test Feedback banner */}
              {testResult && testResult.id === conn.id && (
                <div className={`mt-2 p-2 rounded text-xs border ${
                  testResult.success
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}>
                  <div className="font-medium">{testResult.message}</div>
                  {testResult.latency && <div className="text-[10px] opacity-80">Latency: {testResult.latency}ms</div>}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
              <button
                onClick={() => handleTestConnection(conn.id)}
                disabled={testingId === conn.id}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition disabled:opacity-50"
              >
                <RefreshCw className={`h-3 w-3 ${testingId === conn.id ? 'animate-spin' : ''}`} />
                <span>{testingId === conn.id ? 'Testing...' : 'Test'}</span>
              </button>

              <button
                onClick={() => handleExploreTables(conn)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-brand-600/20 hover:bg-brand-600/30 text-brand-400 border border-brand-500/30 transition"
              >
                <Table className="h-3 w-3" />
                <span>Discover</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Schema Discovery Modal */}
      {selectedTables && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-5 space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Table className="h-4 w-4 text-brand-400" />
                <h3 className="text-sm font-semibold text-white">Discovered Schema: {exploringConnName}</h3>
              </div>
              <button onClick={() => setSelectedTables(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            {selectedTables.length === 0 ? (
              <div className="py-6 text-center text-slate-500 text-xs">No tables found in this connection.</div>
            ) : (
              <div className="space-y-3">
                {selectedTables.map((tbl, idx) => (
                  <div key={idx} className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white">{tbl.name}</span>
                      <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">{tbl.table_type}</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 text-[11px] text-slate-400">
                      {tbl.columns.map((c: any, cidx: number) => (
                        <div key={cidx} className="bg-slate-900 px-2 py-1 rounded border border-slate-800/80 flex items-center justify-between font-mono">
                          <span className={c.is_primary_key ? 'text-amber-400 font-bold' : 'text-slate-300'}>{c.name}</span>
                          <span className="text-[9px] text-slate-500">{c.data_type}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add Connection Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-white">Register Connection</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateConnection} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Connection Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Sales Warehouse Destination"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Connector Engine</label>
                <select
                  value={formType}
                  onChange={(e) => {
                    setFormType(e.target.value);
                    if (e.target.value === 'mysql') {
                      setFormPort('3306');
                      setFormUser('root');
                    } else if (e.target.value === 'postgres') {
                      setFormPort('5432');
                      setFormUser('postgres');
                    }
                  }}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="postgres">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                  <option value="sqlite">SQLite</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">Host</label>
                  <input
                    type="text"
                    required
                    value={formHost}
                    onChange={(e) => setFormHost(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Port</label>
                  <input
                    type="number"
                    required
                    value={formPort}
                    onChange={(e) => setFormPort(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 mb-1">User</label>
                  <input
                    type="text"
                    required
                    value={formUser}
                    onChange={(e) => setFormUser(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Password</label>
                  <input
                    type="password"
                    value={formPassword}
                    onChange={(e) => setFormPassword(e.target.value)}
                    placeholder="Encrypted via Fernet"
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Database Name</label>
                <input
                  type="text"
                  required
                  value={formDatabase}
                  onChange={(e) => setFormDatabase(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded transition disabled:opacity-50"
                >
                  {isSaving ? 'Saving...' : 'Save Connection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
