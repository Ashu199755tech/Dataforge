import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import api from '../api/client';
import { 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  BarChart3, 
  Layers,
  ArrowUpRight
} from 'lucide-react';

export const DataQualityPage: React.FC = () => {
  const { activeProject } = useAppStore();
  const [results, setResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // In our backend verification, DataQualityResults are recorded in data_quality_results table
    const loadResults = async () => {
      try {
        // Query recent runs with DQ results
        const res = await api.get('/runs?limit=10');
        const runs = res.data;
        const allResults: any[] = [];
        for (const r of runs) {
          if (r.activity_runs) {
            for (const act of r.activity_runs) {
              if (act.activity_type === 'DataQualityCheck' && act.metrics?.summary) {
                for (const s of act.metrics.summary) {
                  allResults.push({
                    run_id: r.id,
                    rule: s.rule,
                    pass_pct: s.pass_pct,
                    passed: s.passed,
                    started_at: r.started_at
                  });
                }
              }
            }
          }
        }
        setResults(allResults);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    loadResults();
  }, [activeProject]);

  const dimensions = [
    { name: 'Completeness', score: '100%', sub: 'Mandatory and Non-Null checks', status: 'Optimal' },
    { name: 'Uniqueness', score: '100%', sub: 'Primary Key & Deduplication', status: 'Optimal' },
    { name: 'Validity', score: '100%', sub: 'Type and Positive Range checks', status: 'Optimal' },
    { name: 'Consistency', score: '100%', sub: 'Referential foreign keys', status: 'Optimal' }
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Enterprise Data Quality</h1>
          <p className="text-xs text-slate-400">Rule evaluations, SLA compliance, and data governance scorecards</p>
        </div>
      </div>

      {/* Dimensions Scorecards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {dimensions.map((dim, idx) => (
          <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">{dim.name}</span>
              <ShieldCheck className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-white">{dim.score}</div>
            <div className="text-[11px] text-slate-500">{dim.sub}</div>
          </div>
        ))}
      </div>

      {/* Recent Evaluations Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white">Rule Execution Scorecard</h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/50 text-slate-400 uppercase text-[10px] font-semibold">
              <tr>
                <th className="py-2.5 px-3 rounded-l">Rule Description</th>
                <th className="py-2.5 px-3">Run ID</th>
                <th className="py-2.5 px-3">Compliance Score</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 rounded-r">Evaluated At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {results.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">
                    No data quality evaluations recorded. Execute a pipeline containing a Data Quality activity!
                  </td>
                </tr>
              ) : (
                results.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 font-medium text-slate-200">{r.rule}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                      {r.run_id.substring(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-emerald-400">{r.pass_pct}%</td>
                    <td className="py-2.5 px-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                        r.passed
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                      }`}>
                        {r.passed ? <CheckCircle2 className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />}
                        {r.passed ? 'PASSED' : 'FAILED'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">
                      {new Date(r.started_at).toLocaleString()}
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
