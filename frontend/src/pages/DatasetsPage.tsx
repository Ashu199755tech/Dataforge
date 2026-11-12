import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { useAppStore } from '../store/useAppStore';
import { ListFilterSortBar } from '../components/common/ListFilterSortBar';
import { 
  Layers, 
  Database, 
  HardDrive, 
  Plus, 
  RefreshCw, 
  Search, 
  AlertTriangle, 
  CheckCircle2, 
  Eye, 
  FileText, 
  Trash2, 
  GitFork, 
  History, 
  ArrowRight, 
  Check, 
  Table, 
  Sliders, 
  Cloud,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  Zap,
  Info,
  ArrowLeft
} from 'lucide-react';

export interface ColumnItem {
  name: string;
  type: string;
  nullable: boolean;
  description?: string;
}

export interface DatasetItem {
  id: string;
  project_id?: string;
  connection_id: string;
  connection_name?: string;
  connector_type?: string;
  name: string;
  description?: string;
  dataset_type: string;
  location_config: Record<string, any>;
  format_settings: Record<string, any>;
  parameters: Record<string, any>;
  schema_definition: ColumnItem[];
  current_version: number;
  schema_status: 'Current' | 'DriftDetected' | 'NeedsSync';
  last_drift_check_at?: string;
  last_drift_summary?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface DriftReport {
  has_drift: boolean;
  status: string;
  added_columns: ColumnItem[];
  removed_columns: ColumnItem[];
  altered_columns: Array<{ name: string; stored_type: string; physical_type: string; change: string }>;
  current_physical_schema: ColumnItem[];
  stored_schema: ColumnItem[];
}

export const DatasetsPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [sortBy, setSortBy] = useState<string>('newest');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [selectedDatasetForSchema, setSelectedDatasetForSchema] = useState<DatasetItem | null>(null);
  const [schemaTab, setSchemaTab] = useState<'schema' | 'drift' | 'versions'>('schema');
  const [driftReport, setDriftReport] = useState<DriftReport | null>(null);
  const [checkingDrift, setCheckingDrift] = useState(false);
  const [versions, setVersions] = useState<any[]>([]);
  
  // Preview Modal
  const [previewDataset, setPreviewDataset] = useState<DatasetItem | null>(null);
  const [previewRows, setPreviewRows] = useState<any[]>([]);
  const [previewCols, setPreviewCols] = useState<string[]>([]);
  const [previewLimit, setPreviewLimit] = useState(25);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewMeta, setPreviewMeta] = useState<{ bytes: number; duration: number } | null>(null);

  // Usages Modal
  const [usagesDataset, setUsagesDataset] = useState<DatasetItem | null>(null);
  const [usagesData, setUsagesData] = useState<any>(null);
  const [loadingUsages, setLoadingUsages] = useState(false);

  // Create Form State
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formType, setFormType] = useState('RelationalTable');
  const [formConnectionId, setFormConnectionId] = useState('');
  const [formTable, setFormTable] = useState('');
  const [formSchema, setFormSchema] = useState('');
  const [formContainer, setFormContainer] = useState('');
  const [formPath, setFormPath] = useState('');
  const [formFormat, setFormFormat] = useState('delimited');
  const [formDelimiter, setFormDelimiter] = useState(',');
  const [formHasHeader, setFormHasHeader] = useState(true);
  const [formDiscoveredCols, setFormDiscoveredCols] = useState<ColumnItem[]>([]);
  const [discoveringSchema, setDiscoveringSchema] = useState(false);
  const [submittingCreate, setSubmittingCreate] = useState(false);

  const fetchData = async () => {
    try {
      setRefreshing(true);
      const [dsRes, connRes] = await Promise.all([
        api.get('/datasets'),
        api.get('/connections')
      ]);
      setDatasets(dsRes.data);
      setConnections(connRes.data);
    } catch (err) {
      console.error('Failed to load datasets', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenCreateModal = () => {
    setWizardStep(1);
    setFormName('');
    setFormDesc('');
    setFormType('RelationalTable');
    setFormConnectionId(connections.length > 0 ? connections[0].id : '');
    setFormTable('');
    setFormSchema('');
    setFormContainer('');
    setFormPath('');
    setFormFormat('delimited');
    setFormDelimiter(',');
    setFormHasHeader(true);
    setFormDiscoveredCols([]);
    setShowCreateModal(true);
  };

  const handleAutoDiscoverInWizard = async () => {
    if (!formConnectionId) {
      alert('Please select a connection first');
      return;
    }
    setDiscoveringSchema(true);
    try {
      const selectedConn = connections.find(c => c.id === formConnectionId);
      const isStorage = ['azure_blob', 'azure_adls', 'aws_s3', 'gcp_storage', 'local_storage'].includes(selectedConn?.connector_type);

      if (isStorage) {
        if (!formContainer) {
          alert('Please enter a container/bucket name first');
          setDiscoveringSchema(false);
          return;
        }
        // Preview sample file to infer columns
        const res = await api.post(`/connections/${formConnectionId}/storage/preview`, {
          container: formContainer,
          path: formPath,
          format: formFormat,
          limit: 10
        });
        const cols: ColumnItem[] = (res.data.columns || []).map((colName: string) => ({
          name: colName,
          type: 'VARCHAR',
          nullable: true
        }));
        setFormDiscoveredCols(cols);
      } else {
        if (!formTable) {
          alert('Please enter a table name first');
          setDiscoveringSchema(false);
          return;
        }
        const res = await api.get(`/connections/${formConnectionId}/tables/${formTable}/columns`, {
          params: formSchema ? { schema_name: formSchema } : {}
        });
        const cols: ColumnItem[] = (res.data.columns || []).map((c: any) => ({
          name: c.name,
          type: String(c.data_type || 'VARCHAR').toUpperCase(),
          nullable: c.is_nullable !== undefined ? c.is_nullable : true,
          description: c.comment
        }));
        setFormDiscoveredCols(cols);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Schema discovery failed. You may add columns manually.');
    } finally {
      setDiscoveringSchema(false);
    }
  };

  const handleSubmitCreate = async () => {
    if (!formName.trim() || !formConnectionId) return;

    setSubmittingCreate(true);
    try {
      const location_config: Record<string, any> = {};
      const format_settings: Record<string, any> = {};

      if (formType === 'RelationalTable' || formType === 'RelationalQuery') {
        location_config.table = formTable.trim();
        if (formSchema.trim()) location_config.schema = formSchema.trim();
      } else {
        location_config.container = formContainer.trim();
        location_config.path = formPath.trim();
        format_settings.format = formFormat;
        format_settings.delimiter = formDelimiter;
        format_settings.has_header = formHasHeader;
      }

      await api.post('/datasets', {
        name: formName.trim(),
        description: formDesc.trim() || undefined,
        dataset_type: formType,
        connection_id: formConnectionId,
        location_config,
        format_settings,
        schema_definition: formDiscoveredCols,
        auto_discover_schema: formDiscoveredCols.length === 0
      });

      setShowCreateModal(false);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create dataset');
    } finally {
      setSubmittingCreate(false);
    }
  };

  const handleOpenSchemaDrawer = async (ds: DatasetItem) => {
    setSelectedDatasetForSchema(ds);
    setSchemaTab('schema');
    setDriftReport(null);
    try {
      const vRes = await api.get(`/datasets/${ds.id}/versions`);
      setVersions(vRes.data);
    } catch (err) {
      console.error('Failed to load dataset versions', err);
    }
  };

  const handleCheckDrift = async (dsId: string) => {
    setCheckingDrift(true);
    try {
      const res = await api.post(`/datasets/${dsId}/detect-drift`);
      setDriftReport(res.data);
      setSchemaTab('drift');
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to run drift detection');
    } finally {
      setCheckingDrift(false);
    }
  };

  const handleSyncSchema = async (dsId: string) => {
    try {
      await api.post(`/datasets/${dsId}/sync-schema`, { notes: 'Accepted detected schema drift' });
      await fetchData();
      const updated = datasets.find(d => d.id === dsId);
      if (updated) setSelectedDatasetForSchema(updated);
      setSchemaTab('schema');
      setDriftReport(null);
      alert('Dataset schema synchronized successfully to latest version!');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Schema synchronization failed');
    }
  };

  const handleOpenPreview = async (ds: DatasetItem) => {
    setPreviewDataset(ds);
    setLoadingPreview(true);
    try {
      const res = await api.post(`/datasets/${ds.id}/preview`, { row_limit: previewLimit });
      setPreviewCols(res.data.columns || []);
      setPreviewRows(res.data.rows || []);
      setPreviewMeta({ bytes: res.data.bytes_sampled, duration: res.data.duration_ms });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to preview dataset data');
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleOpenUsages = async (ds: DatasetItem) => {
    setUsagesDataset(ds);
    setLoadingUsages(true);
    try {
      const res = await api.get(`/datasets/${ds.id}/usages`);
      setUsagesData(res.data);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load dataset usage dependencies');
    } finally {
      setLoadingUsages(false);
    }
  };

  const handleDeleteDataset = async (dsId: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete dataset '${name}'? This cannot be undone.`)) return;
    try {
      await api.delete(`/datasets/${dsId}`);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete dataset');
    }
  };

  const filteredDatasets = datasets.filter(ds => {
    const matchesSearch = ds.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (ds.description || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (ds.connection_name || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === 'all' || 
                        (typeFilter === 'relational' && (ds.dataset_type === 'RelationalTable' || ds.dataset_type === 'RelationalQuery')) ||
                        (typeFilter === 'file' && ds.dataset_type !== 'RelationalTable' && ds.dataset_type !== 'RelationalQuery');
    return matchesSearch && matchesType;
  });

  // Default: Newest items appear on top
  const sortedDatasets = [...filteredDatasets].sort((a, b) => {
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
      const cmp = a.name.localeCompare(b.name);
      return sortDirection === 'asc' ? cmp : -cmp;
    }
    if (sortBy === 'name_desc') {
      const cmp = b.name.localeCompare(a.name);
      return sortDirection === 'asc' ? cmp : -cmp;
    }
    if (sortBy === 'type') {
      const cmp = (a.dataset_type || '').localeCompare(b.dataset_type || '');
      return sortDirection === 'asc' ? cmp : -cmp;
    }
    return 0;
  });

  const totalRelational = datasets.filter(d => d.dataset_type === 'RelationalTable' || d.dataset_type === 'RelationalQuery').length;
  const totalFiles = datasets.length - totalRelational;
  const totalDrift = datasets.filter(d => d.schema_status === 'DriftDetected').length;

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
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
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                Reusable Dataset Management
                <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">
                  Enterprise Catalog
                </span>
              </h1>
              <p className="text-slate-400 text-sm mt-0.5">
                Centralized metadata, automated schema inference, drift detection, and reusable source/sink contracts.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 rounded-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-lg shadow-emerald-600/20 transition"
          >
            <Plus className="w-4 h-4" />
            New Dataset
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Total Catalog Datasets</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{datasets.length}</span>
            <span className="text-xs text-slate-500">defined</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Reusable across all Copy Data activities
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Relational Tables & Views</span>
            <Database className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{totalRelational}</span>
            <span className="text-xs text-slate-500">datasets</span>
          </div>
          <div className="mt-2 text-[11px] text-blue-400">
            Postgres, MySQL, Snowflake, SQL Server
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Multi-Cloud File Datasets</span>
            <Cloud className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{totalFiles}</span>
            <span className="text-xs text-slate-500">datasets</span>
          </div>
          <div className="mt-2 text-[11px] text-purple-400">
            Parquet, CSV, JSON, Avro on S3/ADLS/GCS
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Schema Drift Alerts</span>
            <AlertTriangle className={`w-4 h-4 ${totalDrift > 0 ? 'text-amber-400' : 'text-slate-500'}`} />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className={`text-2xl font-bold ${totalDrift > 0 ? 'text-amber-400' : 'text-slate-100'}`}>
              {totalDrift}
            </span>
            <span className="text-xs text-slate-500">drift detected</span>
          </div>
          <div className={`mt-2 text-[11px] ${totalDrift > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {totalDrift > 0 ? 'Physical source altered' : 'All schemas in sync'}
          </div>
        </div>
      </div>

      {/* Filters & Search & Sort */}
      <ListFilterSortBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search datasets by name, connection, or location..."
        currentSort={sortBy}
        onSortChange={setSortBy}
        sortDirection={sortDirection}
        onToggleDirection={() => setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
        sortOptions={[
          { id: 'newest', label: 'Newest First' },
          { id: 'oldest', label: 'Oldest First' },
          { id: 'name_asc', label: 'Name (A to Z)' },
          { id: 'name_desc', label: 'Name (Z to A)' },
          { id: 'type', label: 'Dataset Type' }
        ]}
        totalCount={datasets.length}
        filteredCount={sortedDatasets.length}
      >
        <div className="flex items-center gap-1.5 bg-slate-950/70 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setTypeFilter('all')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
              typeFilter === 'all'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            All Types ({datasets.length})
          </button>
          <button
            onClick={() => setTypeFilter('relational')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
              typeFilter === 'relational'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Relational ({totalRelational})
          </button>
          <button
            onClick={() => setTypeFilter('file')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
              typeFilter === 'file'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Cloud Files ({totalFiles})
          </button>
        </div>
      </ListFilterSortBar>

      {/* Dataset List Table */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-500 mb-2" />
            Loading reusable datasets...
          </div>
        ) : sortedDatasets.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            No datasets found. Click "New Dataset" to register a reusable dataset contract.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3">Dataset Name</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Connection Reference</th>
                  <th className="px-6 py-3">Target Location</th>
                  <th className="px-6 py-3">Schema & Version</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {sortedDatasets.map((ds) => {
                  const isRelational = ds.dataset_type === 'RelationalTable' || ds.dataset_type === 'RelationalQuery';
                  const isDrift = ds.schema_status === 'DriftDetected';

                  return (
                    <tr 
                      key={ds.id} 
                      onClick={() => handleOpenSchemaDrawer(ds)}
                      className={`cursor-pointer transition-colors group ${
                        selectedDatasetForSchema?.id === ds.id 
                          ? 'bg-emerald-950/20 border-l-2 border-emerald-500' 
                          : 'hover:bg-slate-800/40'
                      }`}
                    >
                      {/* Name */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors text-sm flex items-center gap-2">
                          {ds.name}
                        </div>
                        {ds.description && (
                          <div className="text-slate-400 text-[11px] mt-0.5 truncate max-w-xs">
                            {ds.description}
                          </div>
                        )}
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                          ID: {ds.id.slice(0, 13)}... • Click to inspect schema & drift
                        </div>
                      </td>

                      {/* Type Badge */}
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
                          isRelational
                            ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                        }`}>
                          {isRelational ? <Database className="w-3 h-3" /> : <HardDrive className="w-3 h-3" />}
                          {ds.dataset_type}
                        </span>
                      </td>

                      {/* Connection */}
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-200">
                          {ds.connection_name || 'Connection'}
                        </div>
                        <div className="text-[10px] text-slate-500 uppercase font-mono">
                          {ds.connector_type || 'database'}
                        </div>
                      </td>

                      {/* Location */}
                      <td className="px-6 py-4 font-mono text-[11px] text-slate-300">
                        {isRelational ? (
                          <span>
                            {ds.location_config?.schema ? `${ds.location_config.schema}.` : ''}
                            {ds.location_config?.table || ds.location_config?.table_name || 'table'}
                          </span>
                        ) : (
                          <span>
                            {ds.location_config?.container || ds.location_config?.bucket}/
                            {ds.location_config?.path || ds.location_config?.file_name}
                          </span>
                        )}
                      </td>

                      {/* Schema & Version */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleOpenSchemaDrawer(ds)}
                            className="font-mono text-emerald-400 hover:underline flex items-center gap-1"
                          >
                            v{ds.current_version} ({ds.schema_definition?.length || 0} cols)
                          </button>
                        </div>
                      </td>

                      {/* Drift Status */}
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                          isDrift
                            ? 'bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse'
                            : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        }`}>
                          {isDrift ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                          {ds.schema_status}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right space-x-1" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleOpenPreview(ds)}
                          title="Preview Sample Data"
                          className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-800 rounded transition"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleCheckDrift(ds.id)}
                          title="Detect Schema Drift"
                          className="p-1.5 text-slate-400 hover:text-amber-400 hover:bg-slate-800 rounded transition"
                        >
                          <RefreshCw className={`w-4 h-4 ${checkingDrift ? 'animate-spin text-amber-400' : ''}`} />
                        </button>
                        <button
                          onClick={() => handleOpenUsages(ds)}
                          title="View Pipeline Dependencies"
                          className="p-1.5 text-slate-400 hover:text-blue-400 hover:bg-slate-800 rounded transition"
                        >
                          <GitFork className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteDataset(ds.id, ds.name)}
                          title="Delete Dataset"
                          className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL 1: CREATE DATASET WIZARD */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <Plus className="w-4 h-4 text-emerald-400" />
                  Create Reusable Dataset — Step {wizardStep} of 3
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Define reusable connection, table/file location, and schema contract.
                </p>
              </div>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>

            {/* Step Indicators */}
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              {[
                { step: 1, label: '1. Identity & Type' },
                { step: 2, label: '2. Location & Format' },
                { step: 3, label: '3. Schema Discovery' }
              ].map(s => (
                <button
                  key={s.step}
                  onClick={() => setWizardStep(s.step)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                    wizardStep === s.step
                      ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {/* STEP 1: Identity & Connection */}
            {wizardStep === 1 && (
              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Dataset Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. ds_sales_orders"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Description</label>
                  <input
                    type="text"
                    placeholder="e.g. Daily consolidated transaction table from ERP database"
                    value={formDesc}
                    onChange={(e) => setFormDesc(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Connection Reference *</label>
                  <select
                    value={formConnectionId}
                    onChange={(e) => setFormConnectionId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  >
                    {connections.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.connector_type})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Dataset Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setFormType('RelationalTable')}
                      className={`p-3 rounded-xl border text-left flex items-center gap-3 transition ${
                        formType === 'RelationalTable'
                          ? 'bg-blue-500/10 border-blue-500/40 text-blue-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <Database className="w-5 h-5 text-blue-400 shrink-0" />
                      <div>
                        <div className="font-semibold text-xs">Relational Table</div>
                        <div className="text-[10px] text-slate-500">Postgres, MySQL, SQLite, Snowflake</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setFormType('DelimitedText')}
                      className={`p-3 rounded-xl border text-left flex items-center gap-3 transition ${
                        formType !== 'RelationalTable'
                          ? 'bg-purple-500/10 border-purple-500/40 text-purple-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <HardDrive className="w-5 h-5 text-purple-400 shrink-0" />
                      <div>
                        <div className="font-semibold text-xs">Cloud File / Object Storage</div>
                        <div className="text-[10px] text-slate-500">S3, ADLS Gen2, GCS (Parquet, CSV, JSON)</div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* STEP 2: Location & Settings */}
            {wizardStep === 2 && (
              <div className="space-y-4 text-xs">
                {formType === 'RelationalTable' ? (
                  <>
                    <div>
                      <label className="block text-slate-300 font-medium mb-1">Schema Name (Optional)</label>
                      <input
                        type="text"
                        placeholder="e.g. public or dbo"
                        value={formSchema}
                        onChange={(e) => setFormSchema(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-300 font-medium mb-1">Table Name *</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. customers or fact_orders"
                        value={formTable}
                        onChange={(e) => setFormTable(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-slate-300 font-medium mb-1">Container / S3 Bucket *</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. raw-data or landing-zone"
                        value={formContainer}
                        onChange={(e) => setFormContainer(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-300 font-medium mb-1">File Path / Prefix *</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. telemetry/orders.parquet or exports/@{formatDateTime(utcnow(),'yyyy-MM-dd')}/"
                        value={formPath}
                        onChange={(e) => setFormPath(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-slate-300 font-medium mb-1">File Format</label>
                        <select
                          value={formFormat}
                          onChange={(e) => setFormFormat(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                        >
                          <option value="delimited">Delimited Text (CSV/TSV)</option>
                          <option value="parquet">Apache Parquet</option>
                          <option value="json">JSON</option>
                          <option value="jsonl">JSON Lines</option>
                          <option value="avro">Apache Avro</option>
                          <option value="orc">Apache ORC</option>
                          <option value="excel">Excel (.xlsx)</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-slate-300 font-medium mb-1">Delimiter</label>
                        <input
                          type="text"
                          value={formDelimiter}
                          onChange={(e) => setFormDelimiter(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                        />
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* STEP 3: Schema Discovery */}
            {wizardStep === 3 && (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between bg-slate-950 p-3 border border-slate-800 rounded-xl">
                  <div>
                    <div className="font-semibold text-slate-200">Automatic Schema Discovery</div>
                    <div className="text-[11px] text-slate-400">
                      Query the physical table or sample the cloud file to infer column names and data types.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleAutoDiscoverInWizard}
                    disabled={discoveringSchema}
                    className="px-3 py-1.5 bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-600/30 rounded-lg font-semibold flex items-center gap-1.5 transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${discoveringSchema ? 'animate-spin' : ''}`} />
                    {discoveringSchema ? 'Discovering...' : 'Discover Schema'}
                  </button>
                </div>

                {formDiscoveredCols.length > 0 ? (
                  <div className="overflow-y-auto max-h-56 border border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] sticky top-0">
                        <tr>
                          <th className="px-4 py-2">Column Name</th>
                          <th className="px-4 py-2">Data Type</th>
                          <th className="px-4 py-2">Nullable</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {formDiscoveredCols.map((c, idx) => (
                          <tr key={idx} className="hover:bg-slate-800/20">
                            <td className="px-4 py-2 font-mono text-[11px] text-slate-200">{c.name}</td>
                            <td className="px-4 py-2">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">
                                {c.type}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-slate-400">
                              {c.nullable ? 'Yes' : 'No'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-8 text-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
                    Click "Discover Schema" to sample columns, or create dataset now to discover automatically upon first run.
                  </div>
                )}
              </div>
            )}

            {/* Wizard Navigation Footer */}
            <div className="flex justify-between items-center pt-3 border-t border-slate-800">
              {wizardStep > 1 ? (
                <button
                  type="button"
                  onClick={() => setWizardStep(wizardStep - 1)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
                >
                  Back
                </button>
              ) : <div />}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
                >
                  Cancel
                </button>

                {wizardStep < 3 ? (
                  <button
                    type="button"
                    onClick={() => setWizardStep(wizardStep + 1)}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg text-xs transition flex items-center gap-1.5"
                  >
                    Next Step
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleSubmitCreate}
                    disabled={submittingCreate}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg text-xs transition flex items-center gap-1.5"
                  >
                    {submittingCreate ? 'Creating...' : 'Create Dataset'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* DRAWER / MODAL 2: SCHEMA VIEWER & DRIFT DETECTION */}
      {selectedDatasetForSchema && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <Table className="w-5 h-5 text-emerald-400" />
                  Schema Contract & Drift — {selectedDatasetForSchema.name} (v{selectedDatasetForSchema.current_version})
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  View column definitions, inspect schema version history, and detect structural drift against physical storage.
                </p>
              </div>
              <button onClick={() => setSelectedDatasetForSchema(null)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>

            {/* Tab navigation */}
            <div className="flex border-b border-slate-800 text-xs">
              <button
                onClick={() => setSchemaTab('schema')}
                className={`px-4 py-2 font-semibold border-b-2 transition ${
                  schemaTab === 'schema'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                Schema Columns ({selectedDatasetForSchema.schema_definition?.length || 0})
              </button>
              <button
                onClick={() => setSchemaTab('drift')}
                className={`px-4 py-2 font-semibold border-b-2 transition flex items-center gap-1.5 ${
                  schemaTab === 'drift'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                Drift Detection
                {selectedDatasetForSchema.schema_status === 'DriftDetected' && (
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                )}
              </button>
              <button
                onClick={() => setSchemaTab('versions')}
                className={`px-4 py-2 font-semibold border-b-2 transition ${
                  schemaTab === 'versions'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                Version Snapshots ({versions.length})
              </button>
            </div>

            {/* TAB 1: CURRENT SCHEMA DEFINITION */}
            {schemaTab === 'schema' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">
                    Status: <strong className="text-emerald-400">{selectedDatasetForSchema.schema_status}</strong>
                  </span>
                  <button
                    onClick={() => handleCheckDrift(selectedDatasetForSchema.id)}
                    disabled={checkingDrift}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs flex items-center gap-1.5 transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${checkingDrift ? 'animate-spin' : ''}`} />
                    Check Live Source Drift
                  </button>
                </div>

                <div className="overflow-y-auto max-h-72 border border-slate-800 rounded-xl">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] sticky top-0">
                      <tr>
                        <th className="px-4 py-2.5">#</th>
                        <th className="px-4 py-2.5">Column Name</th>
                        <th className="px-4 py-2.5">Data Type</th>
                        <th className="px-4 py-2.5">Nullable</th>
                        <th className="px-4 py-2.5">Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {selectedDatasetForSchema.schema_definition?.map((c, i) => (
                        <tr key={i} className="hover:bg-slate-800/20">
                          <td className="px-4 py-2 text-slate-500 font-mono text-[10px]">{i + 1}</td>
                          <td className="px-4 py-2 font-mono text-slate-200 font-semibold">{c.name}</td>
                          <td className="px-4 py-2">
                            <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-slate-800 text-emerald-400 border border-slate-700">
                              {c.type}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-slate-400">{c.nullable ? 'Nullable' : 'Not Null'}</td>
                          <td className="px-4 py-2 text-slate-500 italic text-[11px]">{c.description || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 2: SCHEMA DRIFT ANALYSIS */}
            {schemaTab === 'drift' && (
              <div className="space-y-4 text-xs">
                {driftReport ? (
                  driftReport.has_drift ? (
                    <div className="space-y-3">
                      <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl text-amber-300 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          <span>
                            Physical source has drifted! Detected {driftReport.added_columns.length} added, {driftReport.removed_columns.length} removed, and {driftReport.altered_columns.length} altered columns.
                          </span>
                        </div>
                        <button
                          onClick={() => handleSyncSchema(selectedDatasetForSchema.id)}
                          className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-semibold transition"
                        >
                          Sync & Increment Version
                        </button>
                      </div>

                      {driftReport.added_columns.length > 0 && (
                        <div>
                          <div className="font-semibold text-emerald-400 text-xs mb-1">Added Columns in Source:</div>
                          <div className="flex flex-wrap gap-1.5">
                            {driftReport.added_columns.map(c => (
                              <span key={c.name} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 rounded font-mono text-[11px]">
                                + {c.name} ({c.type})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {driftReport.removed_columns.length > 0 && (
                        <div>
                          <div className="font-semibold text-red-400 text-xs mb-1">Removed Columns from Source:</div>
                          <div className="flex flex-wrap gap-1.5">
                            {driftReport.removed_columns.map(c => (
                              <span key={c.name} className="px-2 py-0.5 bg-red-500/10 border border-red-500/30 text-red-300 rounded font-mono text-[11px]">
                                - {c.name} ({c.type})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {driftReport.altered_columns.length > 0 && (
                        <div>
                          <div className="font-semibold text-amber-400 text-xs mb-1">Altered Column Types:</div>
                          <div className="space-y-1">
                            {driftReport.altered_columns.map(c => (
                              <div key={c.name} className="p-2 bg-slate-950 border border-slate-800 rounded font-mono text-[11px] text-slate-300">
                                {c.change}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="p-8 text-center text-slate-400 border border-slate-800 rounded-xl space-y-2">
                      <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                      <div className="font-semibold text-slate-200">No Schema Drift Detected</div>
                      <div className="text-[11px] text-slate-500">
                        The current physical table/file structure exactly matches stored schema version {selectedDatasetForSchema.current_version}.
                      </div>
                    </div>
                  )
                ) : (
                  <div className="p-8 text-center text-slate-500 border border-slate-800 rounded-xl space-y-3">
                    <RefreshCw className="w-8 h-8 mx-auto text-slate-600" />
                    <div>Click below to connect to the physical data source and inspect for added, deleted, or changed columns.</div>
                    <button
                      onClick={() => handleCheckDrift(selectedDatasetForSchema.id)}
                      disabled={checkingDrift}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg transition"
                    >
                      {checkingDrift ? 'Checking Drift...' : 'Run Drift Analysis'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: VERSION HISTORY */}
            {schemaTab === 'versions' && (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {versions.map(v => (
                  <div key={v.id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                    <div>
                      <div className="font-semibold text-slate-200 flex items-center gap-2">
                        <span>Version {v.version_number}</span>
                        <span className="font-mono text-[10px] text-slate-500">
                          ({v.schema_snapshot?.length || 0} columns)
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {v.change_summary || 'Snapshot created'}
                      </div>
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {new Date(v.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setSelectedDatasetForSchema(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: BOUNDED DATA PREVIEW */}
      {previewDataset && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <Eye className="w-5 h-5 text-emerald-400" />
                  Data Preview — {previewDataset.name}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Safe, memory-bounded row preview sampled from live connector.
                </p>
              </div>
              <button onClick={() => setPreviewDataset(null)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Rows to sample:</span>
                {[10, 25, 50, 100].map(lim => (
                  <button
                    key={lim}
                    onClick={() => {
                      setPreviewLimit(lim);
                      handleOpenPreview({ ...previewDataset });
                    }}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono transition ${
                      previewLimit === lim
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {lim}
                  </button>
                ))}
              </div>

              {previewMeta && (
                <div className="text-[11px] text-slate-400 font-mono">
                  Sampled {previewRows.length} rows in {previewMeta.duration}ms ({Math.round(previewMeta.bytes / 1024)} KB)
                </div>
              )}
            </div>

            {loadingPreview ? (
              <div className="py-20 text-center text-slate-500 text-xs">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-500 mb-2" />
                Streaming preview chunks...
              </div>
            ) : previewRows.length === 0 ? (
              <div className="py-20 text-center text-slate-500 text-xs">
                No records returned by source connector.
              </div>
            ) : (
              <div className="overflow-x-auto max-h-96 border border-slate-800 rounded-xl">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] sticky top-0">
                    <tr>
                      <th className="px-4 py-2 border-r border-slate-800/60 w-12 text-center">#</th>
                      {previewCols.map(col => (
                        <th key={col} className="px-4 py-2 font-mono">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {previewRows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30">
                        <td className="px-4 py-1.5 border-r border-slate-800/60 text-center font-mono text-[10px] text-slate-500">
                          {idx + 1}
                        </td>
                        {previewCols.map(col => (
                          <td key={col} className="px-4 py-1.5 font-mono text-[11px] text-slate-200 whitespace-nowrap">
                            {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-slate-600">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setPreviewDataset(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: USAGE & DEPENDENCY INFORMATION */}
      {usagesDataset && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <GitFork className="w-5 h-5 text-blue-400" />
                  Dataset Usages — {usagesDataset.name}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Pipelines and activities actively referencing this dataset.
                </p>
              </div>
              <button onClick={() => setUsagesDataset(null)} className="text-slate-400 hover:text-slate-200">✕</button>
            </div>

            {loadingUsages ? (
              <div className="py-12 text-center text-slate-500 text-xs">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto text-blue-500 mb-2" />
                Scanning pipelines...
              </div>
            ) : !usagesData || usagesData.pipeline_count === 0 ? (
              <div className="py-12 text-center text-slate-500 text-xs">
                No pipelines currently reference this dataset.
              </div>
            ) : (
              <div className="space-y-3 max-h-72 overflow-y-auto">
                {usagesData.pipelines.map((p: any) => (
                  <div key={p.pipeline_id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
                    <div className="font-semibold text-slate-200 text-xs flex items-center justify-between">
                      <span>{p.pipeline_name}</span>
                      <span className="text-[10px] text-slate-500 font-mono">ID: {p.pipeline_id.slice(0, 8)}</span>
                    </div>
                    <div className="space-y-1">
                      {p.activities.map((a: any) => (
                        <div key={a.activity_id} className="flex items-center justify-between text-[11px] text-slate-400 pl-2 border-l border-slate-800">
                          <span>{a.activity_name} ({a.activity_type})</span>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
                            a.role === 'Source'
                              ? 'bg-blue-500/20 text-blue-400'
                              : 'bg-emerald-500/20 text-emerald-400'
                          }`}>
                            {a.role}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setUsagesDataset(null)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
