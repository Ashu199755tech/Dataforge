import React, { useEffect, useState } from 'react';
import { 
  ArrowRightLeft, 
  FileCode, 
  ShieldCheck, 
  Search, 
  Clock, 
  Variable, 
  GitFork, 
  Globe,
  Cpu,
  Layers,
  Sparkles,
  FileSearch,
  Trash2,
  Repeat,
  Workflow,
  Split,
  Filter,
  AlertOctagon,
  ListPlus,
  RotateCw,
  Terminal,
  DatabaseZap,
  CloudLightning,
  Flame,
  Send,
  CheckCheck,
  FolderCog,
  Archive,
  BarChart3,
  Scale,
  ShieldAlert,
  Boxes,
  Radio
} from 'lucide-react';
import api from '../../api/client';

interface DynamicActivity {
  activity_type: string;
  display_name: string;
  category: string;
  description: string;
  icon: string;
}

const DEFAULT_ACTIVITIES = [
  {
    category: 'Move & Transform',
    items: [
      { type: 'CopyData', label: 'Copy Data', icon: ArrowRightLeft, color: 'text-brand-400', desc: 'Stream from source to destination' },
      { type: 'ExecuteDataFlow', label: 'Data Flow', icon: Workflow, color: 'text-brand-400', desc: 'Vectorized mapping transformation graph' },
      { type: 'Lookup', label: 'Lookup', icon: Search, color: 'text-teal-400', desc: 'Read dataset or single record' },
      { type: 'CDCReplication', label: 'CDC Replication', icon: Radio, color: 'text-rose-400', desc: 'Transaction log stream replication' },
      { type: 'GetMetadata', label: 'Get Metadata', icon: FileSearch, color: 'text-indigo-400', desc: 'Inspect table/file structure & rows' },
      { type: 'DeleteData', label: 'Delete Data', icon: Trash2, color: 'text-rose-400', desc: 'Cleanup records or truncate tables' },
    ]
  },
  {
    category: 'Data Quality & Governance',
    items: [
      { type: 'DataQualityCheck', label: 'Data Quality', icon: ShieldCheck, color: 'text-purple-400', desc: 'Enforce SLAs, rules & quarantine' },
      { type: 'DataProfiling', label: 'Data Profiling', icon: BarChart3, color: 'text-cyan-400', desc: 'Exhaustive column metrics & stats' },
      { type: 'Reconciliation', label: 'Reconciliation', icon: Scale, color: 'text-emerald-400', desc: 'Source-to-target parity & checksums' },
      { type: 'DataMasking', label: 'Data Masking', icon: ShieldAlert, color: 'text-rose-400', desc: 'Redact & mask sensitive PII columns' },
    ]
  },
  {
    category: 'Control Flow',
    items: [
      { type: 'IfCondition', label: 'If Condition', icon: GitFork, color: 'text-orange-400', desc: 'Evaluate conditions & branch' },
      { type: 'ForEach', label: 'ForEach', icon: Repeat, color: 'text-emerald-400', desc: 'Loop over array items in seq/par' },
      { type: 'ExecutePipeline', label: 'Execute Pipeline', icon: Workflow, color: 'text-violet-400', desc: 'Invoke child pipeline & wait' },
      { type: 'Switch', label: 'Switch', icon: Split, color: 'text-yellow-400', desc: 'Route execution by case value' },
      { type: 'Filter', label: 'Filter', icon: Filter, color: 'text-blue-400', desc: 'Filter array by boolean expression' },
      { type: 'SetVariable', label: 'Set Variable', icon: Variable, color: 'text-cyan-400', desc: 'Assign pipeline variable' },
      { type: 'AppendVariable', label: 'Append Variable', icon: ListPlus, color: 'text-teal-400', desc: 'Append item to array variable' },
      { type: 'Wait', label: 'Wait', icon: Clock, color: 'text-amber-400', desc: 'Pause execution for N seconds' },
      { type: 'Until', label: 'Until', icon: RotateCw, color: 'text-pink-400', desc: 'Loop until condition is met' },
      { type: 'Validation', label: 'Validation', icon: CheckCheck, color: 'text-lime-400', desc: 'Verify dataset or file existence' },
      { type: 'Fail', label: 'Fail', icon: AlertOctagon, color: 'text-red-500', desc: 'Trigger deliberate pipeline error' },
    ]
  },
  {
    category: 'Compute & External',
    items: [
      { type: 'SqlScript', label: 'SQL Script', icon: FileCode, color: 'text-emerald-400', desc: 'Execute queries on connection' },
      { type: 'PythonScript', label: 'Python Script', icon: Terminal, color: 'text-emerald-400', desc: 'Run sandboxed Python code' },
      { type: 'StoredProcedure', label: 'Stored Procedure', icon: DatabaseZap, color: 'text-purple-400', desc: 'Execute database routine or function' },
      { type: 'CustomActivity', label: 'Custom Activity', icon: Cpu, color: 'text-amber-400', desc: 'Execute custom command/binary' },
      { type: 'DatabricksNotebook', label: 'Databricks Notebook', icon: CloudLightning, color: 'text-orange-400', desc: 'Run Databricks notebook job' },
      { type: 'Dbt', label: 'dbt Transformation', icon: Boxes, color: 'text-orange-500', desc: 'Run dbt Core models or dbt Cloud jobs' },
      { type: 'ReverseETL', label: 'Reverse ETL', icon: Send, color: 'text-indigo-400', desc: 'Sync to Salesforce, HubSpot, Slack' },
      { type: 'PySparkJob', label: 'PySpark Job', icon: Flame, color: 'text-rose-400', desc: 'Submit Apache Spark / PySpark job' },
      { type: 'WebActivity', label: 'Web Activity', icon: Globe, color: 'text-sky-400', desc: 'Send HTTP request & capture response' },
      { type: 'Webhook', label: 'Webhook', icon: Send, color: 'text-teal-400', desc: 'Call endpoint with async callback URL' },
      { type: 'RestApi', label: 'REST API Call', icon: Globe, color: 'text-sky-400', desc: 'Invoke external HTTP webhooks' },
    ]
  },
  {
    category: 'File & Storage',
    items: [
      { type: 'FileOperation', label: 'File Operation', icon: FolderCog, color: 'text-amber-400', desc: 'Copy, move, delete, rename files' },
      { type: 'Archive', label: 'Archive & Unzip', icon: Archive, color: 'text-indigo-400', desc: 'Compress to zip or extract archives' },
    ]
  }
];

const getIconComponent = (iconName: string) => {
  switch (iconName?.toLowerCase()) {
    case 'arrowrightleft':
      return ArrowRightLeft;
    case 'search':
      return Search;
    case 'shieldcheck':
      return ShieldCheck;
    case 'gitfork':
      return GitFork;
    case 'variable':
      return Variable;
    case 'clock':
      return Clock;
    case 'filecode':
      return FileCode;
    case 'globe':
      return Globe;
    case 'cpu':
      return Cpu;
    case 'filesearch':
      return FileSearch;
    case 'trash2':
      return Trash2;
    case 'repeat':
      return Repeat;
    case 'workflow':
      return Workflow;
    case 'split':
      return Split;
    case 'filter':
      return Filter;
    case 'alertoctagon':
      return AlertOctagon;
    case 'listplus':
      return ListPlus;
    case 'rotatecw':
      return RotateCw;
    case 'terminal':
      return Terminal;
    case 'databasezap':
      return DatabaseZap;
    case 'cloudlightning':
      return CloudLightning;
    case 'flame':
      return Flame;
    case 'send':
      return Send;
    case 'checkcheck':
      return CheckCheck;
    case 'foldercog':
      return FolderCog;
    case 'archive':
      return Archive;
    case 'barchart3':
      return BarChart3;
    case 'scale':
      return Scale;
    case 'shieldalert':
      return ShieldAlert;
    default:
      return Layers;
  }
};

const getColorClass = (type: string) => {
  switch (type.toLowerCase()) {
    case 'copydata': return 'text-brand-400';
    case 'lookup': return 'text-teal-400';
    case 'getmetadata': return 'text-indigo-400';
    case 'deletedata': return 'text-rose-400';
    case 'dataqualitycheck': return 'text-purple-400';
    case 'dataquality': return 'text-purple-400';
    case 'dataprofiling': return 'text-cyan-400';
    case 'reconciliation': return 'text-emerald-400';
    case 'datamasking': return 'text-rose-400';
    case 'executedataflow': return 'text-brand-400';
    case 'ifcondition': return 'text-orange-400';
    case 'foreach': return 'text-emerald-400';
    case 'executepipeline': return 'text-violet-400';
    case 'switch': return 'text-yellow-400';
    case 'filter': return 'text-blue-400';
    case 'fail': return 'text-red-500';
    case 'setvariable': return 'text-cyan-400';
    case 'appendvariable': return 'text-teal-400';
    case 'wait': return 'text-amber-400';
    case 'until': return 'text-pink-400';
    case 'sqlscript': return 'text-emerald-400';
    case 'pythonscript': return 'text-emerald-400';
    case 'storedprocedure': return 'text-purple-400';
    case 'customactivity': return 'text-amber-400';
    case 'databricksnotebook': return 'text-orange-400';
    case 'pysparkjob': return 'text-rose-400';
    case 'webactivity': return 'text-sky-400';
    case 'webhook': return 'text-teal-400';
    case 'validation': return 'text-lime-400';
    case 'fileoperation': return 'text-amber-400';
    case 'archive': return 'text-indigo-400';
    case 'restapi': return 'text-sky-400';
    default: return 'text-slate-400';
  }
};

export const ActivityToolbox: React.FC = () => {
  const [categories, setCategories] = useState(DEFAULT_ACTIVITIES);

  useEffect(() => {
    const loadDynamicActivities = async () => {
      try {
        const res = await api.get<DynamicActivity[]>('/activities');
        if (res.data && res.data.length > 0) {
          // Group activities by category
          const grouped: Record<string, any[]> = {};
          res.data.forEach((act) => {
            const cat = act.category || 'General';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push({
              type: act.activity_type,
              label: act.display_name,
              icon: getIconComponent(act.icon),
              color: getColorClass(act.activity_type),
              desc: act.description
            });
          });

          const formatted = Object.keys(grouped).map((catName) => ({
            category: catName,
            items: grouped[catName]
          }));

          setCategories(formatted);
        }
      } catch (err) {
        // Fall back gracefully to built-in default catalog
        console.debug('Using local default activity catalogue', err);
      }
    };

    loadDynamicActivities();
  }, []);

  const onDragStart = (event: React.DragEvent, nodeType: string, label: string) => {
    event.dataTransfer.setData('application/reactflow-type', nodeType);
    event.dataTransfer.setData('application/reactflow-label', label);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 p-4 space-y-4 shrink-0 flex flex-col justify-between select-none overflow-y-auto">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Activity Toolbox</h3>
            <p className="text-[11px] text-slate-500">Drag activities onto the canvas</p>
          </div>
          <span className="p-1 rounded bg-brand-500/10 text-brand-400 text-[10px] font-mono border border-brand-500/20 flex items-center gap-1" title="Dynamic Registry Active">
            <Sparkles className="h-3 w-3" />
            <span>Registry</span>
          </span>
        </div>

        {categories.map((cat, idx) => (
          <div key={idx} className="space-y-2">
            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              {cat.category}
            </div>
            <div className="space-y-1.5">
              {cat.items.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, item.type, item.label)}
                    className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/40 cursor-grab active:cursor-grabbing transition space-y-1 group"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className={`h-4 w-4 ${item.color} group-hover:scale-110 transition`} />
                      <span className="text-xs font-semibold text-slate-200">{item.label}</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">{item.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-400">
        <span className="font-semibold text-slate-300">Canvas Tip:</span> Connect handles to build conditional dependency DAGs.
      </div>
    </div>
  );
};
