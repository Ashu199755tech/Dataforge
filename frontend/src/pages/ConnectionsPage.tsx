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
  Table,
  Cloud,
  Layers,
  HardDrive,
  FolderTree,
  ShieldCheck
} from 'lucide-react';

export const ConnectionsPage: React.FC = () => {
  const { connections, activeProject, fetchConnections } = useAppStore();
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string; latency?: number } | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedTables, setSelectedTables] = useState<any[] | null>(null);
  const [exploringConnName, setExploringConnName] = useState<string>('');

  // General Form state
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('postgres');
  
  // Relational Form state
  const [formHost, setFormHost] = useState('localhost');
  const [formPort, setFormPort] = useState('5432');
  const [formUser, setFormUser] = useState('postgres');
  const [formPassword, setFormPassword] = useState('');
  const [formDatabase, setFormDatabase] = useState('postgres');
  
  // Cloud & Object Storage Form state
  const [formAccountName, setFormAccountName] = useState('');
  const [formContainerName, setFormContainerName] = useState('');
  const [formAuthMode, setFormAuthMode] = useState('account_key');
  const [formAccountKey, setFormAccountKey] = useState('');
  const [formSasToken, setFormSasToken] = useState('');
  const [formClientId, setFormClientId] = useState('');
  const [formClientSecret, setFormClientSecret] = useState('');
  const [formTenantId, setFormTenantId] = useState('');
  const [formCustomEndpoint, setFormCustomEndpoint] = useState('');
  const [formBasePath, setFormBasePath] = useState('./data_storage');
  
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
      let config: Record<string, any> = {};

      if (formType === 'azure_blob') {
        config = {
          account_name: formAccountName,
          container_name: formContainerName || undefined,
          auth_mode: formAuthMode,
          account_key: formAuthMode === 'account_key' ? formAccountKey : undefined,
          sas_token: formAuthMode === 'sas_token' ? formSasToken : undefined,
          client_id: formAuthMode === 'service_principal' || formAuthMode === 'managed_identity' ? formClientId : undefined,
          client_secret: formAuthMode === 'service_principal' ? formClientSecret : undefined,
          tenant_id: formAuthMode === 'service_principal' ? formTenantId : undefined,
          custom_endpoint: formCustomEndpoint || undefined
        };
      } else if (formType === 'azure_adls') {
        config = {
          account_name: formAccountName,
          filesystem: formContainerName || undefined,
          auth_mode: formAuthMode,
          account_key: formAuthMode === 'account_key' ? formAccountKey : undefined,
          sas_token: formAuthMode === 'sas_token' ? formSasToken : undefined,
          client_id: formAuthMode === 'service_principal' || formAuthMode === 'managed_identity' ? formClientId : undefined,
          client_secret: formAuthMode === 'service_principal' ? formClientSecret : undefined,
          tenant_id: formAuthMode === 'service_principal' ? formTenantId : undefined,
          custom_endpoint: formCustomEndpoint || undefined
        };
      } else if (formType === 'local_storage' || formType === 'local_file') {
        config = {
          base_path: formBasePath || './data_storage'
        };
      } else {
        config = {
          host: formHost,
          port: parseInt(formPort),
          user: formUser,
          password: formPassword,
          database: formDatabase
        };
      }

      await api.post('/connections', {
        project_id: activeProject.id,
        name: formName,
        connector_type: formType,
        config
      });
      setShowAddModal(false);
      setFormName('');
      setFormPassword('');
      setFormAccountKey('');
      setFormClientSecret('');
      setFormSasToken('');
      fetchConnections();
    } catch (err: any) {
      alert(`Error creating connection: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const renderConnectorIcon = (type: string) => {
    switch (type) {
      case 'azure_blob':
        return (
          <div className="p-2 rounded-lg border bg-sky-500/10 border-sky-500/30 text-sky-400">
            <Cloud className="h-4 w-4" />
          </div>
        );
      case 'azure_adls':
        return (
          <div className="p-2 rounded-lg border bg-cyan-500/10 border-cyan-500/30 text-cyan-400">
            <FolderTree className="h-4 w-4" />
          </div>
        );
      case 'local_storage':
      case 'local_file':
        return (
          <div className="p-2 rounded-lg border bg-violet-500/10 border-violet-500/30 text-violet-400">
            <HardDrive className="h-4 w-4" />
          </div>
        );
      case 'postgres':
        return (
          <div className="p-2 rounded-lg border bg-blue-500/10 border-blue-500/30 text-blue-400">
            <Database className="h-4 w-4" />
          </div>
        );
      case 'mysql':
        return (
          <div className="p-2 rounded-lg border bg-amber-500/10 border-amber-500/30 text-amber-400">
            <Database className="h-4 w-4" />
          </div>
        );
      default:
        return (
          <div className="p-2 rounded-lg border bg-emerald-500/10 border-emerald-500/30 text-emerald-400">
            <Server className="h-4 w-4" />
          </div>
        );
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Enterprise Connections</h1>
          <p className="text-xs text-slate-400">Multi-cloud storage credentials and live database connectors</p>
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
        {connections.map((conn) => {
          const cfg = conn.config_masked || {};
          const isAzure = conn.connector_type.startsWith('azure_');
          const isLocal = conn.connector_type.includes('local');

          return (
            <div 
              key={conn.id} 
              className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition space-y-4 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    {renderConnectorIcon(conn.connector_type)}
                    <div>
                      <h3 className="text-sm font-semibold text-white">{conn.name}</h3>
                      <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                        {conn.connector_type.replace('_', ' ')}
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

                {/* Masked Endpoint Details */}
                <div className="mt-3 p-2 rounded bg-slate-950/60 border border-slate-800/80 text-[11px] font-mono text-slate-400 space-y-0.5">
                  {isAzure ? (
                    <>
                      <div>Account: <span className="text-slate-300">{cfg.account_name || 'devstoreaccount1'}</span></div>
                      <div>Container/FS: <span className="text-slate-300">{cfg.container_name || cfg.filesystem || 'All'}</span></div>
                      <div>Auth: <span className="text-sky-400">{cfg.auth_mode || 'account_key'}</span></div>
                      {cfg.custom_endpoint && <div>Endpoint: <span className="text-slate-400">{cfg.custom_endpoint}</span></div>}
                    </>
                  ) : isLocal ? (
                    <div>Root Path: <span className="text-slate-300">{cfg.base_path || './data_storage'}</span></div>
                  ) : (
                    <>
                      <div>Host: <span className="text-slate-300">{cfg.host || 'localhost'}</span>:{cfg.port || ''}</div>
                      <div>Database: <span className="text-slate-300">{cfg.database}</span></div>
                      <div>User: <span className="text-slate-300">{cfg.user}</span></div>
                    </>
                  )}
                </div>

                {/* Live Test Feedback banner */}
                {testResult && testResult.id === conn.id && (
                  <div className={`mt-2 p-2 rounded text-xs border ${
                    testResult.success
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  }`}>
                    <div className="font-medium">{testResult.message}</div>
                    {testResult.latency !== undefined && <div className="text-[10px] opacity-80">Latency: {testResult.latency}ms</div>}
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
                  <span>{testingId === conn.id ? 'Testing...' : 'Test Connection'}</span>
                </button>

                <button
                  onClick={() => handleExploreTables(conn)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-brand-600/20 hover:bg-brand-600/30 text-brand-400 border border-brand-500/30 transition"
                >
                  <Table className="h-3 w-3" />
                  <span>Explore Items</span>
                </button>
              </div>
            </div>
          );
        })}
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
              <div className="py-6 text-center text-slate-500 text-xs">No tables or objects found in this connection.</div>
            ) : (
              <div className="space-y-3">
                {selectedTables.map((t: any, idx: number) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-medium text-white">{t.schema_name ? `${t.schema_name}.${t.name}` : t.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">{t.table_type || 'OBJECT'}</span>
                      </div>
                      {t.approx_row_count !== null && (
                        <span className="text-[10px] text-slate-500 font-mono">~{t.approx_row_count} rows</span>
                      )}
                    </div>
                    {t.columns && t.columns.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 pt-1">
                        {t.columns.map((c: any, cidx: number) => (
                          <div key={cidx} className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800/80 flex items-center justify-between">
                            <span className="text-slate-300 truncate">{c.name}</span>
                            <span className="text-slate-500">{c.data_type}</span>
                          </div>
                        ))}
                      </div>
                    )}
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
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white">Create Enterprise Connection</h3>
            <form onSubmit={handleCreateConnection} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Connection Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Azure Datalake Raw, Production Postgres"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Connector Type</label>
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
                  <optgroup label="Cloud Object Storage">
                    <option value="azure_adls">Azure Data Lake Storage Gen2 (ADLS)</option>
                    <option value="azure_blob">Azure Blob Storage</option>
                    <option value="local_storage">Local Filesystem / Mounted Volume</option>
                  </optgroup>
                  <optgroup label="Relational Databases">
                    <option value="postgres">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlite">SQLite</option>
                  </optgroup>
                </select>
              </div>

              {/* Azure ADLS Gen2 & Blob Configuration Fields */}
              {(formType === 'azure_blob' || formType === 'azure_adls') && (
                <div className="space-y-3 p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
                  <div className="flex items-center gap-1.5 text-sky-400 font-medium">
                    <Cloud className="h-3.5 w-3.5" />
                    <span>Azure Cloud Configuration</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-slate-400 mb-1">Storage Account Name</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. dataforgelake"
                        value={formAccountName}
                        onChange={(e) => setFormAccountName(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">{formType === 'azure_adls' ? 'Filesystem / Container' : 'Container Name'}</label>
                      <input
                        type="text"
                        placeholder="e.g. bronze-layer"
                        value={formContainerName}
                        onChange={(e) => setFormContainerName(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1">Authentication Mode</label>
                    <select
                      value={formAuthMode}
                      onChange={(e) => setFormAuthMode(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                    >
                      <option value="account_key">Account Key (SharedKey)</option>
                      <option value="sas_token">Shared Access Signature (SAS)</option>
                      <option value="service_principal">Service Principal (Entra ID / AAD)</option>
                      <option value="managed_identity">Managed Identity (Azure VM / AKS)</option>
                    </select>
                  </div>

                  {formAuthMode === 'account_key' && (
                    <div>
                      <label className="block text-slate-400 mb-1">Account Key</label>
                      <input
                        type="password"
                        required
                        placeholder="Primary / Secondary storage key"
                        value={formAccountKey}
                        onChange={(e) => setFormAccountKey(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      />
                    </div>
                  )}

                  {formAuthMode === 'sas_token' && (
                    <div>
                      <label className="block text-slate-400 mb-1">SAS Token Query String</label>
                      <input
                        type="password"
                        required
                        placeholder="?sv=2020-08-04&ss=b&srt=sco&sp=rwdlac..."
                        value={formSasToken}
                        onChange={(e) => setFormSasToken(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                      />
                    </div>
                  )}

                  {formAuthMode === 'service_principal' && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-400 mb-1">Client ID</label>
                          <input
                            type="text"
                            required
                            placeholder="Application Client UUID"
                            value={formClientId}
                            onChange={(e) => setFormClientId(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Tenant ID</label>
                          <input
                            type="text"
                            required
                            placeholder="Entra ID Tenant UUID"
                            value={formTenantId}
                            onChange={(e) => setFormTenantId(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Client Secret</label>
                        <input
                          type="password"
                          required
                          placeholder="Client Secret Value"
                          value={formClientSecret}
                          onChange={(e) => setFormClientSecret(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                        />
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-slate-400 mb-1">Custom Endpoint (Azurite Emulator / Private Link)</label>
                    <input
                      type="text"
                      placeholder="e.g. http://127.0.0.1:10000/devstoreaccount1"
                      value={formCustomEndpoint}
                      onChange={(e) => setFormCustomEndpoint(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                </div>
              )}

              {/* Local Storage Configuration */}
              {formType === 'local_storage' && (
                <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-2">
                  <label className="block text-slate-400 mb-1">Base Directory Path</label>
                  <input
                    type="text"
                    required
                    placeholder="./data_storage or /mnt/nfs/lake"
                    value={formBasePath}
                    onChange={(e) => setFormBasePath(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  />
                </div>
              )}

              {/* Relational Database Fields */}
              {(formType === 'postgres' || formType === 'mysql' || formType === 'sqlite') && (
                <>
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
                </>
              )}

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
