import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { DashboardMetrics } from '../types';
import api from '../api/client';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Database, 
  GitBranch, 
  TrendingUp, 
  Layers, 
  ArrowRight,
  HardDrive
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid 
} from 'recharts';

export const DashboardPage: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { setCurrentTab, setSelectedPipelineId } = useAppStore();

  const fetchMetrics = async () => {
    try {
      const res = await api.get('/dashboard/metrics');
      setMetrics(res.data);
    } catch (err) {
      console.error('Failed to load dashboard metrics', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading || !metrics) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-400 gap-2">
        <div className="h-5 w-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <span>Loading enterprise telemetry...</span>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Pipelines',
      value: metrics.pipelines.total,
      sub: `${metrics.pipelines.active} Active`,
      icon: GitBranch,
      color: 'from-blue-500/20 to-brand-500/10',
      border: 'border-blue-500/30',
      textColor: 'text-blue-400'
    },
    {
      title: 'Success Rate',
      value: `${metrics.runs.success_rate_percent}%`,
      sub: `${metrics.runs.successful} / ${metrics.runs.total} Executions`,
      icon: TrendingUp,
      color: 'from-emerald-500/20 to-teal-500/10',
      border: 'border-emerald-500/30',
      textColor: 'text-emerald-400'
    },
    {
      title: 'Rows Ingested',
      value: metrics.volume.total_rows_written.toLocaleString(),
      sub: `Extracted: ${metrics.volume.total_rows_read.toLocaleString()}`,
      icon: HardDrive,
      color: 'from-purple-500/20 to-indigo-500/10',
      border: 'border-purple-500/30',
      textColor: 'text-purple-400'
    },
    {
      title: 'Connections',
      value: metrics.connections.total,
      sub: `${metrics.connections.active} Active Healthy`,
      icon: Database,
      color: 'from-amber-500/20 to-orange-500/10',
      border: 'border-amber-500/30',
      textColor: 'text-amber-400'
    }
  ];

  const chartData = [
    { name: 'Successful', count: metrics.runs.successful, fill: '#10b981' },
    { name: 'Failed', count: metrics.runs.failed, fill: '#ef4444' },
    { name: 'Running', count: metrics.runs.running, fill: '#38a8f6' },
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Executive Dashboard</h1>
          <p className="text-xs text-slate-400">Live operational telemetry across pipelines, data throughput, and connectors</p>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={() => setCurrentTab('designer')}
            className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-sm"
          >
            <GitBranch className="h-3.5 w-3.5" />
            <span>New Pipeline</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div 
              key={i} 
              className={`p-4 rounded-xl bg-gradient-to-br ${card.color} bg-slate-900/60 border ${card.border} backdrop-blur-sm`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">{card.title}</span>
                <Icon className={`h-4 w-4 ${card.textColor}`} />
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-white">{card.value}</span>
              </div>
              <div className="mt-1 text-[11px] text-slate-400">{card.sub}</div>
            </div>
          );
        })}
      </div>

      {/* Main Content Grid: Chart & Recent Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Execution Distribution Chart */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Execution Health Status</h2>
            <p className="text-xs text-slate-400">Total pipeline run distribution</p>
          </div>
          <div className="h-56 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} allowDecimals={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-around text-center pt-2 border-t border-slate-800 text-xs">
            <div>
              <div className="font-bold text-emerald-400">{metrics.runs.successful}</div>
              <div className="text-[10px] text-slate-500">Succeeded</div>
            </div>
            <div>
              <div className="font-bold text-rose-400">{metrics.runs.failed}</div>
              <div className="text-[10px] text-slate-500">Failed</div>
            </div>
            <div>
              <div className="font-bold text-brand-400">{metrics.runs.running}</div>
              <div className="text-[10px] text-slate-500">Running</div>
            </div>
          </div>
        </div>

        {/* Recent Executions Table */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white">Recent Pipeline Executions</h2>
              <p className="text-xs text-slate-400">Latest manual and scheduled pipeline runs</p>
            </div>
            <button 
              onClick={() => setCurrentTab('runs')}
              className="text-xs text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-800/50 text-slate-400 uppercase text-[10px] font-semibold tracking-wider">
                <tr>
                  <th className="py-2.5 px-3 rounded-l">Run ID</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Rows Written</th>
                  <th className="py-2.5 px-3">Duration</th>
                  <th className="py-2.5 px-3 rounded-r">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {metrics.recent_activity.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500">
                      No executions recorded yet. Create and run a pipeline!
                    </td>
                  </tr>
                ) : (
                  metrics.recent_activity.map((run) => (
                    <tr key={run.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">
                        {run.id.substring(0, 8)}...
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{run.run_type}</td>
                      <td className="py-2.5 px-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                          run.status === 'Succeeded'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : run.status === 'Failed'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            : 'bg-brand-500/10 text-brand-400 border-brand-500/20'
                        }`}>
                          {run.status === 'Succeeded' ? <CheckCircle2 className="h-2.5 w-2.5" /> : null}
                          {run.status === 'Failed' ? <XCircle className="h-2.5 w-2.5" /> : null}
                          {run.status === 'Running' ? <Clock className="h-2.5 w-2.5 animate-spin" /> : null}
                          {run.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-200">
                        {run.rows_written.toLocaleString()}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{run.duration_seconds}s</td>
                      <td className="py-2.5 px-3 text-slate-500">
                        {new Date(run.started_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
