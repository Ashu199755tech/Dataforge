import React, { useState, useEffect, useRef } from 'react';
import api from '../../api/client';
import {
  X,
  Sparkles,
  Search,
  CheckCircle2,
  AlertTriangle,
  Play,
  Variable,
  Layers,
  Workflow,
  HelpCircle,
  Copy,
  ChevronRight,
  Code2
} from 'lucide-react';

interface ExpressionFunction {
  name: string;
  category: string;
  signature: string;
  description: string;
  example: string;
  return_type: string;
}

interface ExpressionBuilderModalProps {
  isOpen: boolean;
  initialValue: string;
  fieldName?: string;
  onClose: () => void;
  onApply: (expression: string) => void;
  upstreamActivities?: Array<{ id: string; name: string; type: string }>;
  pipelineParameters?: Array<{ name: string; type?: string; defaultValue?: any }>;
  pipelineVariables?: Array<{ name: string; type?: string; defaultValue?: any }>;
}

export const ExpressionBuilderModal: React.FC<ExpressionBuilderModalProps> = ({
  isOpen,
  initialValue,
  fieldName,
  onClose,
  onApply,
  upstreamActivities = [],
  pipelineParameters = [],
  pipelineVariables = []
}) => {
  const [expression, setExpression] = useState(initialValue || '@');
  const [activeTab, setActiveTab] = useState<'functions' | 'parameters' | 'system' | 'activities' | 'preview'>('functions');
  const [functions, setFunctions] = useState<ExpressionFunction[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Validation state
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; error: string | null } | null>(null);

  // Simulation state
  const [simParams, setSimParams] = useState('{\n  "env": "staging",\n  "limit": 100\n}');
  const [simResult, setSimResult] = useState<{ success: boolean; result?: any; error?: string; data_type?: string } | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isOpen) {
      setExpression(initialValue?.startsWith('@') ? initialValue : initialValue ? `@${initialValue}` : '@');
      fetchFunctions();
    }
  }, [isOpen, initialValue]);

  // Real-time validation debounced
  useEffect(() => {
    if (!isOpen || !expression.trim()) return;

    const timer = setTimeout(async () => {
      setIsValidating(true);
      try {
        const res = await api.post('/expressions/validate', { expression });
        setValidationResult(res.data);
      } catch (err: any) {
        setValidationResult({ valid: false, error: err.response?.data?.detail || 'Syntax error' });
      } finally {
        setIsValidating(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [expression, isOpen]);

  const fetchFunctions = async () => {
    try {
      const res = await api.get('/expressions/functions');
      setFunctions(res.data);
    } catch (e) {
      console.error('Failed to load expression functions catalog', e);
    }
  };

  const insertSnippet = (snippet: string) => {
    const textarea = textareaRef.current;
    if (!textarea) {
      setExpression((prev) => prev + snippet);
      return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const current = expression;

    const updated = current.substring(0, start) + snippet + current.substring(end);
    setExpression(updated);

    setTimeout(() => {
      textarea.focus();
      const nextPos = start + snippet.length;
      textarea.setSelectionRange(nextPos, nextPos);
    }, 10);
  };

  const handleSimulate = async () => {
    setIsSimulating(true);
    setSimResult(null);
    try {
      let parsedParams = {};
      try {
        parsedParams = JSON.parse(simParams);
      } catch (e) {
        // ignore parse error for mock
      }

      const res = await api.post('/expressions/evaluate', {
        expression,
        parameters: parsedParams,
        variables: { watermark: '2026-01-01 00:00:00', retry_count: 1 },
        activity_outputs: {
          Lookup: { count: 42, first_row: { id: 101, name: 'Sample Item' } }
        },
        pipeline_info: { RunId: 'sim-run-12345', Pipeline: 'SimPipeline' }
      });
      setSimResult(res.data);
    } catch (err: any) {
      setSimResult({
        success: false,
        error: err.response?.data?.detail || err.message || 'Evaluation failed'
      });
    } finally {
      setIsSimulating(false);
    }
  };

  if (!isOpen) return null;

  const categories = ['All', ...Array.from(new Set(functions.map((f) => f.category)))];

  const filteredFunctions = functions.filter((fn) => {
    const matchesCat = selectedCategory === 'All' || fn.category === selectedCategory;
    const matchesSearch =
      fn.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      fn.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl w-full max-w-4xl flex flex-col max-h-[90vh] overflow-hidden text-slate-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                Add Dynamic Content
                {fieldName && (
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                    {fieldName}
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400">
                Write dynamic expressions, system parameters, or activity references starting with @
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Expression Editor Area */}
        <div className="p-5 border-b border-slate-800 bg-slate-950/20">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Code2 className="w-4 h-4 text-indigo-400" />
              Dynamic Content Expression
            </label>
            <div className="flex items-center gap-2">
              {isValidating ? (
                <span className="text-xs text-slate-400 animate-pulse">Validating syntax...</span>
              ) : validationResult?.valid ? (
                <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Valid Syntax
                </span>
              ) : validationResult?.error ? (
                <span className="flex items-center gap-1 text-xs text-rose-400 bg-rose-950/50 px-2 py-0.5 rounded border border-rose-800/40 truncate max-w-xs" title={validationResult.error}>
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  {validationResult.error}
                </span>
              ) : null}
            </div>
          </div>
          <textarea
            ref={textareaRef}
            value={expression}
            onChange={(e) => setExpression(e.target.value)}
            rows={4}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm font-mono text-indigo-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 resize-none shadow-inner"
            placeholder="@concat('dataset_', formatDateTime(utcNow(), 'yyyyMMdd'), '.parquet')"
            spellCheck={false}
          />
        </div>

        {/* Tabs Selection */}
        <div className="flex items-center px-6 border-b border-slate-800 bg-slate-900/60 gap-1 text-sm font-medium">
          <button
            onClick={() => setActiveTab('functions')}
            className={`px-4 py-3 border-b-2 flex items-center gap-2 transition ${
              activeTab === 'functions'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Code2 className="w-4 h-4" />
            Functions ({functions.length})
          </button>
          <button
            onClick={() => setActiveTab('parameters')}
            className={`px-4 py-3 border-b-2 flex items-center gap-2 transition ${
              activeTab === 'parameters'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Variable className="w-4 h-4" />
            Parameters & Variables
          </button>
          <button
            onClick={() => setActiveTab('system')}
            className={`px-4 py-3 border-b-2 flex items-center gap-2 transition ${
              activeTab === 'system'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Workflow className="w-4 h-4" />
            System Variables
          </button>
          <button
            onClick={() => setActiveTab('activities')}
            className={`px-4 py-3 border-b-2 flex items-center gap-2 transition ${
              activeTab === 'activities'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            Activity Outputs ({upstreamActivities.length})
          </button>
          <button
            onClick={() => setActiveTab('preview')}
            className={`px-4 py-3 border-b-2 flex items-center gap-2 transition ${
              activeTab === 'preview'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Play className="w-4 h-4 text-emerald-400" />
            Test Evaluation
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-6 min-h-[280px] max-h-[360px]">
          {/* TAB 1: FUNCTIONS */}
          {activeTab === 'functions' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search functions (e.g. concat, formatDateTime, addDays)..."
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div className="flex items-center gap-1 overflow-x-auto pb-1 max-w-sm">
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-2.5 py-1 text-xs rounded-full border transition whitespace-nowrap ${
                        selectedCategory === cat
                          ? 'bg-indigo-600/30 border-indigo-500 text-indigo-300'
                          : 'bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredFunctions.map((fn) => (
                  <div
                    key={fn.name}
                    onClick={() => insertSnippet(fn.name + '()')}
                    className="p-3 bg-slate-950/60 border border-slate-800 hover:border-indigo-500/50 rounded-lg cursor-pointer transition hover:bg-indigo-950/20 group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-sm font-semibold text-indigo-300 group-hover:text-indigo-200">
                        {fn.name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                        {fn.return_type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-1 mb-1.5">{fn.description}</p>
                    <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 bg-slate-900/80 px-2 py-1 rounded">
                      <span className="truncate">{fn.example}</span>
                      <span className="text-indigo-400 text-[10px] font-sans opacity-0 group-hover:opacity-100 transition">
                        Insert +
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 2: PARAMETERS & VARIABLES */}
          {activeTab === 'parameters' && (
            <div className="space-y-5">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Pipeline Parameters
                </h4>
                {pipelineParameters.length === 0 ? (
                  <div className="p-3 bg-slate-950/40 border border-slate-800/80 rounded-lg text-xs text-slate-500 italic">
                    No pipeline parameters defined. Use standard: <code>@parameters('param_name')</code>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {pipelineParameters.map((p) => (
                      <button
                        key={p.name}
                        onClick={() => insertSnippet(`parameters('${p.name}')`)}
                        className="p-2.5 bg-slate-950 border border-slate-800 hover:border-indigo-500 rounded-lg text-left flex items-center justify-between group transition"
                      >
                        <div>
                          <div className="font-mono text-sm text-indigo-300">{p.name}</div>
                          <div className="text-[11px] text-slate-400">Default: {String(p.defaultValue ?? 'None')}</div>
                        </div>
                        <span className="text-xs text-indigo-400 opacity-0 group-hover:opacity-100">Insert +</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Pipeline Variables
                </h4>
                {pipelineVariables.length === 0 ? (
                  <div className="p-3 bg-slate-950/40 border border-slate-800/80 rounded-lg text-xs text-slate-500 italic">
                    No pipeline variables defined. Use standard: <code>@variables('var_name')</code>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {pipelineVariables.map((v) => (
                      <button
                        key={v.name}
                        onClick={() => insertSnippet(`variables('${v.name}')`)}
                        className="p-2.5 bg-slate-950 border border-slate-800 hover:border-indigo-500 rounded-lg text-left flex items-center justify-between group transition"
                      >
                        <div>
                          <div className="font-mono text-sm text-indigo-300">{v.name}</div>
                          <div className="text-[11px] text-slate-400">Initial: {String(v.defaultValue ?? 'None')}</div>
                        </div>
                        <span className="text-xs text-indigo-400 opacity-0 group-hover:opacity-100">Insert +</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: SYSTEM VARIABLES */}
          {activeTab === 'system' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { name: '@pipeline().RunId', desc: 'Unique execution identifier for current pipeline run', example: '@pipeline().RunId' },
                { name: '@pipeline().Pipeline', desc: 'Name of current pipeline', example: '@pipeline().Pipeline' },
                { name: '@pipeline().WorkspaceId', desc: 'Current enterprise workspace GUID', example: '@pipeline().WorkspaceId' },
                { name: '@pipeline().TriggerType', desc: 'Trigger invocation type (Manual, Schedule, Event)', example: '@pipeline().TriggerType' },
                { name: '@pipeline().TriggerTime', desc: 'UTC timestamp when the pipeline was scheduled/triggered', example: '@pipeline().TriggerTime' },
                { name: '@item()', desc: 'Current iterated object inside a ForEach loop container', example: '@item().filePath' }
              ].map((sys) => (
                <div
                  key={sys.name}
                  onClick={() => insertSnippet(sys.name.replace(/^@/, ''))}
                  className="p-3 bg-slate-950/60 border border-slate-800 hover:border-indigo-500 rounded-lg cursor-pointer transition group"
                >
                  <div className="font-mono text-sm text-indigo-300 font-semibold mb-1 group-hover:text-indigo-200">
                    {sys.name}
                  </div>
                  <p className="text-xs text-slate-400">{sys.desc}</p>
                </div>
              ))}
            </div>
          )}

          {/* TAB 4: ACTIVITY OUTPUTS */}
          {activeTab === 'activities' && (
            <div className="space-y-3">
              {upstreamActivities.length === 0 ? (
                <div className="p-4 bg-slate-950/40 border border-slate-800 rounded-lg text-xs text-slate-400">
                  No upstream activities found in this pipeline graph. Connect an upstream activity to reference its output properties.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2.5">
                  {upstreamActivities.map((act) => (
                    <div key={act.id} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-white">{act.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                            {act.type}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 mt-1 font-mono">
                          ID: {act.id}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => insertSnippet(`activity('${act.id}').output`)}
                          className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded border border-slate-700 font-mono transition"
                        >
                          .output
                        </button>
                        <button
                          onClick={() => insertSnippet(`activity('${act.id}').output.first_row`)}
                          className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded border border-slate-700 font-mono transition"
                        >
                          .first_row
                        </button>
                        <button
                          onClick={() => insertSnippet(`activity('${act.id}').output.count`)}
                          className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded border border-slate-700 font-mono transition"
                        >
                          .count
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 5: TEST SIMULATION */}
          {activeTab === 'preview' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-slate-400 block mb-1">
                    Simulated Parameters (JSON)
                  </label>
                  <textarea
                    value={simParams}
                    onChange={(e) => setSimParams(e.target.value)}
                    rows={6}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    onClick={handleSimulate}
                    disabled={isSimulating}
                    className="mt-2 w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition"
                  >
                    <Play className="w-3.5 h-3.5" />
                    {isSimulating ? 'Evaluating...' : 'Run Test Evaluation'}
                  </button>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-400 block mb-1">
                    Evaluation Result
                  </label>
                  <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 min-h-[140px] text-xs font-mono">
                    {simResult ? (
                      simResult.success ? (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between border-b border-slate-800 pb-1">
                            <span className="text-emerald-400 font-semibold flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Success
                            </span>
                            <span className="text-slate-500">Type: {simResult.data_type}</span>
                          </div>
                          <pre className="text-indigo-200 overflow-x-auto whitespace-pre-wrap">
                            {typeof simResult.result === 'object'
                              ? JSON.stringify(simResult.result, null, 2)
                              : String(simResult.result)}
                          </pre>
                        </div>
                      ) : (
                        <div className="text-rose-400 space-y-1">
                          <div className="font-semibold flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" /> Error
                          </div>
                          <p>{simResult.error}</p>
                        </div>
                      )
                    ) : (
                      <span className="text-slate-500 italic">
                        Click "Run Test Evaluation" to preview expression output.
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950/60">
          <div className="text-xs text-slate-500 flex items-center gap-1.5 font-mono">
            <span>Tip: Strings starting with @ are evaluated as expressions. Escaped with @@</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                onApply(expression);
                onClose();
              }}
              className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-lg shadow-indigo-600/30 transition flex items-center gap-1.5"
            >
              Apply Dynamic Content
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
