import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '../store/useAppStore';
import api from '../api/client';
import { ListFilterSortBar, SortOption } from '../components/common/ListFilterSortBar';
import { 
  ShieldCheck, 
  ShieldAlert,
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  BarChart3, 
  Layers, 
  ArrowLeft,
  Sparkles,
  RotateCw
} from 'lucide-react';

export const DataQualityPage: React.FC = () => {
  const { activeProject } = useAppStore();
  const [results, setResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadResults = async () => {
    try {
      setIsLoading(true);
      const allResults: any[] = [];

      // 1. Fetch recent pipeline runs
      const res = await api.get('/runs?limit=20');
      const runs = res.data || [];
      for (const r of runs) {
        if (r.activity_runs) {
          for (const act of r.activity_runs) {
            const actType = act.activity_type;
            const metrics = act.metrics || act.output_variables || {};

            if (actType === 'DQAssessActivity') {
              const ruleMetrics = metrics.ruleMetrics || {};
              const ruleKeys = Object.keys(ruleMetrics);
              if (ruleKeys.length > 0) {
                for (const rk of ruleKeys) {
                  const rm = ruleMetrics[rk];
                  allResults.push({
                    run_id: r.id,
                    activity_name: act.activity_name || 'DQ Assess',
                    activity_type: 'DQAssessActivity',
                    rule_id: rk,
                    rule: `${rk}: ${rm.rule_type || 'Rule'} on ${rm.target_column || 'dataset'}`,
                    target_col: rm.target_column || '-',
                    rule_type: rm.rule_type || 'Custom',
                    pass_pct: typeof rm.pass_pct === 'number' ? rm.pass_pct : 100,
                    passed: Boolean(rm.passed),
                    fail_count: rm.fail_count || 0,
                    started_at: act.started_at || r.started_at
                  });
                }
              } else if (metrics.overallDQI !== undefined) {
                allResults.push({
                  run_id: r.id,
                  activity_name: act.activity_name || 'DQ Assess',
                  activity_type: 'DQAssessActivity',
                  rule_id: 'OVERALL',
                  rule: `Assessment: ${act.activity_name || 'Dataset Quality'}`,
                  target_col: 'Overall',
                  rule_type: 'DQI Gate',
                  pass_pct: Math.round((metrics.overallDQI ?? 1) * 100),
                  passed: Boolean(metrics.gatePassed ?? true),
                  fail_count: (metrics.softRejectRows || 0) + (metrics.hardRejectRows || 0),
                  started_at: act.started_at || r.started_at
                });
              }
            } else if (actType === 'DQEnforceActivity') {
              allResults.push({
                run_id: r.id,
                activity_name: act.activity_name || 'DQ Enforce',
                activity_type: 'DQEnforceActivity',
                rule_id: 'ENFORCE',
                rule: `Enforcement: ${act.activity_name || 'Remediation'} (${metrics.cleansedRows || 0} cleansed)`,
                target_col: metrics.writeStrategy || 'merge',
                rule_type: 'Cleansing & Sinks',
                pass_pct: Math.round((metrics.overallDQI ?? 1) * 100),
                passed: Boolean(metrics.gatePassed ?? true),
                cleansed_rows: metrics.cleansedRows || 0,
                soft_reject_rows: metrics.softRejectRows || 0,
                hard_reject_rows: metrics.hardRejectRows || 0,
                fail_count: (metrics.softRejectRows || 0) + (metrics.hardRejectRows || 0),
                started_at: act.started_at || r.started_at
              });
            } else if (actType === 'DataQualityCheck' && metrics.summary) {
              for (const s of metrics.summary) {
                allResults.push({
                  run_id: r.id,
                  activity_name: act.activity_name || 'DQ Check',
                  activity_type: 'DataQualityCheck',
                  rule_id: s.rule_id || 'LEGACY',
                  rule: s.rule || 'Data Quality Check',
                  target_col: s.column || '-',
                  rule_type: s.rule_type || 'Validation',
                  pass_pct: s.pass_pct || 100,
                  passed: Boolean(s.passed),
                  started_at: act.started_at || r.started_at
                });
              }
            }
          }
        }
      }

      // 2. Also query backend FactDQExecutionLog if available
      try {
        const execRes = await api.get('/data-quality/execution-logs?limit=30');
        const execLogs = execRes.data || [];
        for (const el of execLogs) {
          const exists = allResults.some(
            (item) => item.run_id === el.pipeline_run_id && item.activity_type === el.activity_type
          );
          if (!exists) {
            allResults.push({
              run_id: el.pipeline_run_id || el.id,
              activity_name: el.dataset_name || el.activity_type,
              activity_type: el.activity_type,
              rule_id: 'AUDIT',
              rule: `${el.activity_type === 'DQEnforceActivity' ? 'Enforcement' : 'Assessment'} on ${el.dataset_name}`,
              target_col: el.dataset_name,
              rule_type: el.activity_type,
              pass_pct: Math.round((el.overall_dqi || 1) * 100),
              passed: Boolean(el.gate_passed),
              cleansed_rows: el.cleansed_records || 0,
              fail_count: (el.soft_reject_records || 0) + (el.hard_reject_records || 0),
              started_at: el.executed_at
            });
          }
        }
      } catch {
        // Optional endpoint, fail gracefully
      }

      setResults(allResults);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadResults();
  }, [activeProject]);

  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [statusFilter, setStatusFilter] = useState<'all' | 'passed' | 'failed'>('all');

  const dqSortOptions: SortOption[] = [
    { id: 'newest', label: 'Newest First' },
    { id: 'oldest', label: 'Oldest First' },
    { id: 'rule', label: 'Rule Description (A-Z)' },
    { id: 'score', label: 'Compliance Score' },
    { id: 'status', label: 'Evaluation Status' },
  ];

  const filteredAndSortedResults = useMemo(() => {
    const list = results.filter((r) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        r.rule.toLowerCase().includes(q) ||
        r.run_id.toLowerCase().includes(q) ||
        (r.activity_name && r.activity_name.toLowerCase().includes(q)) ||
        (r.target_col && r.target_col.toLowerCase().includes(q));
      const matchesStatus =
        statusFilter === 'all' || (statusFilter === 'passed' ? r.passed : !r.passed);
      return matchesSearch && matchesStatus;
    });

    list.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'newest': {
          const tA = a.started_at ? new Date(a.started_at).getTime() : 0;
          const tB = b.started_at ? new Date(b.started_at).getTime() : 0;
          cmp = tB - tA;
          break;
        }
        case 'oldest': {
          const tA = a.started_at ? new Date(a.started_at).getTime() : 0;
          const tB = b.started_at ? new Date(b.started_at).getTime() : 0;
          cmp = tA - tB;
          break;
        }
        case 'rule':
          cmp = a.rule.localeCompare(b.rule);
          break;
        case 'score':
          cmp = (b.pass_pct || 0) - (a.pass_pct || 0);
          break;
        case 'status':
          cmp = a.passed === b.passed ? 0 : a.passed ? -1 : 1;
          break;
        default: {
          const tA = a.started_at ? new Date(a.started_at).getTime() : 0;
          const tB = b.started_at ? new Date(b.started_at).getTime() : 0;
          cmp = tB - tA;
          break;
        }
      }
      return sortDirection === 'asc' ? -cmp : cmp;
    });

    return list;
  }, [results, searchQuery, sortBy, sortDirection, statusFilter]);

  // Dynamic Dimension calculations based on evaluated rules
  const dimensions = useMemo(() => {
    const calcScore = (predicate: (r: any) => boolean) => {
      const matches = results.filter(predicate);
      if (matches.length === 0) return { score: '100%', status: 'Optimal' };
      const avg = matches.reduce((acc, r) => acc + (r.pass_pct || 0), 0) / matches.length;
      const formatted = `${Math.round(avg)}%`;
      const status = avg >= 95 ? 'Optimal' : avg >= 80 ? 'Warning' : 'Critical';
      return { score: formatted, status };
    };

    const completeness = calcScore(
      (r) =>
        r.rule_id?.startsWith('ATR1') ||
        r.rule_id?.startsWith('ATR2') ||
        r.rule.toLowerCase().includes('null') ||
        r.rule.toLowerCase().includes('blank')
    );

    const uniqueness = calcScore(
      (r) =>
        r.rule_id?.startsWith('DS1') ||
        r.rule.toLowerCase().includes('unique') ||
        r.rule.toLowerCase().includes('duplicate')
    );

    const validity = calcScore(
      (r) =>
        r.rule_id?.startsWith('ATR3') ||
        r.rule_id?.startsWith('ATR4') ||
        r.rule_id?.startsWith('ATR5') ||
        r.rule_id?.startsWith('ATR6') ||
        r.rule_id?.startsWith('ATR7') ||
        r.rule_id?.startsWith('ATR8') ||
        r.rule.toLowerCase().includes('range') ||
        r.rule.toLowerCase().includes('pattern')
    );

    const consistency = calcScore(
      (r) =>
        r.rule_id?.startsWith('CSQL') ||
        r.rule.toLowerCase().includes('referential') ||
        r.rule.toLowerCase().includes('foreign')
    );

    return [
      { name: 'Completeness', score: completeness.score, sub: 'ATR1 Not-Null & ATR2 Non-Blank', status: completeness.status },
      { name: 'Uniqueness', score: uniqueness.score, sub: 'DS1 Primary Key & Window Count', status: uniqueness.status },
      { name: 'Validity', score: validity.score, sub: 'ATR3-8 Range, Domain & Regex Purity', status: validity.status },
      { name: 'Consistency', score: consistency.score, sub: 'CSQL Referential Integrity Join', status: consistency.status },
    ];
  }, [results]);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
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
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white tracking-tight">Enterprise Data Quality</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-semibold">
                ADF Architecture
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Rulebook metadata compiler, 2-phase tagger, automated remediation, and DQI compliance scorecard
            </p>
          </div>
        </div>

        <button
          onClick={loadResults}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition disabled:opacity-50"
        >
          <RotateCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-purple-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Dimensions Scorecards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {dimensions.map((dim, idx) => (
          <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">{dim.name}</span>
              <ShieldCheck className="h-4 w-4 text-purple-400" />
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-2xl font-bold text-white">{dim.score}</span>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  dim.status === 'Optimal'
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : dim.status === 'Warning'
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                }`}
              >
                {dim.status}
              </span>
            </div>
            <div className="text-[11px] text-slate-500">{dim.sub}</div>
          </div>
        ))}
      </div>

      {/* Recent Evaluations Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-white">Rule Execution Scorecard</h3>
            <span className="text-[11px] text-slate-400 bg-slate-800 px-2 py-0.5 rounded-md font-mono">
              {results.length} total check(s)
            </span>
          </div>
          <span className="text-xs text-slate-500">Live Telemetry & Audit Logs</span>
        </div>

        <ListFilterSortBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search DQ rules by ID, column, activity..."
          currentSort={sortBy}
          onSortChange={setSortBy}
          sortDirection={sortDirection}
          onToggleDirection={() => setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
          sortOptions={dqSortOptions}
          totalCount={results.length}
          filteredCount={filteredAndSortedResults.length}
        >
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {(['all', 'passed', 'failed'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 text-xs rounded-lg font-medium transition ${
                  statusFilter === st
                    ? 'bg-brand-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800 hover:border-slate-700'
                }`}
              >
                {st === 'all' ? 'All Evaluations' : st === 'passed' ? 'Passed Only' : 'Failed Only'}
              </button>
            ))}
          </div>
        </ListFilterSortBar>

        <div className="overflow-x-auto rounded-lg border border-slate-800/80">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/50 text-slate-400 uppercase text-[10px] font-semibold">
              <tr>
                <th className="py-2.5 px-3 rounded-l">Engine Activity</th>
                <th className="py-2.5 px-3">Rule / Description</th>
                <th className="py-2.5 px-3">Target / Column</th>
                <th className="py-2.5 px-3">Run ID</th>
                <th className="py-2.5 px-3">Compliance Score</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 rounded-r">Evaluated At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredAndSortedResults.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    {results.length === 0 ? (
                      <div className="space-y-1">
                        <p>No data quality evaluations recorded yet.</p>
                        <p className="text-[11px] text-slate-600">
                          Add a <strong className="text-purple-400">DQ Assess</strong> or <strong className="text-indigo-400">DQ Enforce</strong> activity to your pipeline and run it!
                        </p>
                      </div>
                    ) : (
                      <div>
                        No evaluations matched your search criteria.
                        <button
                          onClick={() => {
                            setSearchQuery('');
                            setStatusFilter('all');
                          }}
                          className="block mx-auto mt-2 text-brand-400 hover:underline"
                        >
                          Clear filters
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ) : (
                filteredAndSortedResults.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition">
                    <td className="py-2.5 px-3 font-medium">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${
                          r.activity_type === 'DQEnforceActivity'
                            ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                            : r.activity_type === 'DQAssessActivity'
                            ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        }`}
                      >
                        {r.activity_type === 'DQEnforceActivity' ? (
                          <ShieldAlert className="h-3 w-3" />
                        ) : (
                          <ShieldCheck className="h-3 w-3" />
                        )}
                        {r.activity_type === 'DQEnforceActivity'
                          ? 'DQ Enforce'
                          : r.activity_type === 'DQAssessActivity'
                          ? 'DQ Assess'
                          : 'DQ Check'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-200">
                      <div>{r.rule}</div>
                      {r.cleansed_rows !== undefined && r.cleansed_rows > 0 && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-mono mt-0.5">
                          <Sparkles className="h-2.5 w-2.5" />
                          {r.cleansed_rows} cell remediation(s)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">
                      {r.target_col || '-'}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                      {r.run_id?.substring(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-emerald-400">
                      <div className="flex items-center gap-1.5">
                        <span>{r.pass_pct}%</span>
                        <div className="w-12 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              r.pass_pct >= 95
                                ? 'bg-emerald-500'
                                : r.pass_pct >= 80
                                ? 'bg-amber-500'
                                : 'bg-rose-500'
                            }`}
                            style={{ width: `${Math.min(r.pass_pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                          r.passed
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        }`}
                      >
                        {r.passed ? (
                          <CheckCircle2 className="h-2.5 w-2.5" />
                        ) : (
                          <XCircle className="h-2.5 w-2.5" />
                        )}
                        {r.passed ? 'PASSED' : 'FAILED'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
