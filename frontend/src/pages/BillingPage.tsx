import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { useAppStore } from '../store/useAppStore';
import { 
  CreditCard, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Sparkles, 
  TrendingUp, 
  Clock, 
  ShieldCheck, 
  Server, 
  Layers, 
  ArrowUpRight, 
  Zap, 
  Check, 
  HelpCircle, 
  Calendar, 
  DollarSign, 
  RefreshCw,
  Sliders,
  ChevronRight,
  Download,
  FileText,
  Building,
  Info
} from 'lucide-react';
import { 
  BillingOverview, 
  SubscriptionPlan, 
  CustomerSubscription,
  PipelineUsageLedgerEntry
} from '../types';

export const BillingPage: React.FC = () => {
  const { activeWorkspace } = useAppStore();
  const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'usage' | 'consumption' | 'breakdown' | 'invoices' | 'estimator'>('overview');
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [recentRuns, setRecentRuns] = useState<any[]>([]);
  const [usageLedger, setUsageLedger] = useState<PipelineUsageLedgerEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUpdatingSub, setIsUpdatingSub] = useState<boolean>(false);
  const [billingPeriodToggle, setBillingPeriodToggle] = useState<'Monthly' | 'Annual'>('Monthly');
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null);

  // Filters for Usage Ledger
  const [filterEngine, setFilterEngine] = useState<string>('ALL');
  const [filterClassification, setFilterClassification] = useState<string>('ALL');
  const [filterBillable, setFilterBillable] = useState<string>('ALL');

  // Estimator State
  const [estRuns, setEstRuns] = useState<number>(35000);
  const [estActivities, setEstActivities] = useState<number>(8);
  const [estSparkHours, setEstSparkHours] = useState<number>(20);
  const [estPeriod, setEstPeriod] = useState<'Monthly' | 'Annual'>('Monthly');

  const fetchData = async () => {
    setIsLoading(true);
    setActionErrorMsg(null);
    try {
      const [overviewRes, plansRes, runsRes, usageRes] = await Promise.all([
        api.get('/billing/overview'),
        api.get('/billing/plans'),
        api.get('/runs?limit=15').catch(() => ({ data: [] })),
        api.get('/billing/usage?limit=50').catch(() => ({ data: [] }))
      ]);

      setOverview(overviewRes.data);
      setPlans(plansRes.data);
      setRecentRuns(runsRes.data || []);
      setUsageLedger(usageRes.data || []);
      if (overviewRes.data?.billing_period) {
        setBillingPeriodToggle(overviewRes.data.billing_period as 'Monthly' | 'Annual');
      }
    } catch (err: any) {
      console.error('Failed to load billing details', err);
      setActionErrorMsg(err.response?.data?.detail || 'Unable to retrieve billing metadata.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeWorkspace]);

  const handlePlanSwitch = async (planId: string, period: 'Monthly' | 'Annual') => {
    setIsUpdatingSub(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      await api.post('/billing/subscription', {
        plan_id: planId,
        billing_period: period,
        workspace_id: activeWorkspace?.id
      });
      setActionSuccessMsg('Subscription successfully updated!');
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 5000);
    } catch (err: any) {
      console.error('Failed to update subscription', err);
      setActionErrorMsg(err.response?.data?.detail || 'Subscription switch failed. Ensure administrative privileges.');
    } finally {
      setIsUpdatingSub(false);
    }
  };

  const handleOverrideBillability = async (ledgerId: string, currentBillable: boolean) => {
    const nextBillable = !currentBillable;
    const reason = window.prompt(
      `Enter justification for marking run as ${nextBillable ? 'Billable' : 'Non-Billable'}:`,
      nextBillable ? 'Reclassified after manual customer inspection' : 'Goodwill adjustment / Infrastructure failure'
    );
    if (!reason) return;

    try {
      await api.post(`/billing/usage/${ledgerId}/override`, {
        is_billable: nextBillable,
        reason: reason
      });
      setActionSuccessMsg(`Run successfully updated to ${nextBillable ? 'Billable' : 'Non-Billable'}.`);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to override billability', err);
      setActionErrorMsg(err.response?.data?.detail || 'Billability override failed.');
    }
  };

  // Estimator Calculations
  const calculateEstimator = () => {
    let recPlan = 'starter';
    let basePrice = 9999;
    let includedRuns = 10000;
    let overageRate = 0.50;

    if (estActivities >= 2 && estActivities <= 5) overageRate = 0.50;
    else if (estActivities <= 15) overageRate = 1.50;
    else if (estActivities <= 30) overageRate = 3.00;
    else overageRate = 5.00;

    if (estRuns > 50000 || estActivities > 20 || estSparkHours > 50) {
      recPlan = 'enterprise';
      basePrice = estPeriod === 'Annual' ? 999990 / 12 : 99999;
      includedRuns = 250000;
    } else if (estRuns > 10000 || estSparkHours > 0 || estActivities > 5) {
      recPlan = 'professional';
      basePrice = estPeriod === 'Annual' ? 299990 / 12 : 29999;
      includedRuns = 50000;
    } else {
      recPlan = 'starter';
      basePrice = estPeriod === 'Annual' ? 99990 / 12 : 9999;
      includedRuns = 10000;
    }

    const overageRuns = Math.max(0, estRuns - includedRuns);
    const overageCost = overageRuns * overageRate;
    const sparkCost = estSparkHours * 45;
    const totalMonthly = basePrice + overageCost + sparkCost;
    
    // ADF comparison estimate (ADF charges ~$1 per 1000 runs + activity charges + SHIR VM costs)
    const adfEquivalent = Math.max(14000, estRuns * 0.95 + (estActivities * estRuns * 0.05) + (estSparkHours * 85));
    const savingsPercent = Math.max(25, Math.min(65, Math.round(((adfEquivalent - totalMonthly) / adfEquivalent) * 100)));

    return {
      recPlan,
      basePrice,
      includedRuns,
      overageRuns,
      overageCost,
      sparkCost,
      totalMonthly,
      adfEquivalent,
      savingsPercent
    };
  };

  const estResult = calculateEstimator();

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400">
        <RefreshCw className="h-8 w-8 animate-spin text-brand-400 mb-3" />
        <p className="text-sm">Loading billing metrics & pricing tiers...</p>
      </div>
    );
  }

  const consumedPct = overview ? Math.min(100, Math.round((overview.consumed_runs / overview.included_runs) * 100)) : 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
              <CreditCard className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                Billing & Cost Management
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {overview?.subscription_status || 'Active'}
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono">
                  {overview?.deployment_model || 'BYOC'}
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Transparent software subscriptions, execution allowances, and BYOC infrastructure metering.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          <button
            onClick={() => setActiveTab('plans')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 shadow-sm transition"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Change Plan
          </button>
        </div>
      </div>

      {/* Notifications */}
      {actionSuccessMsg && (
        <div className="flex items-center gap-2 p-3 bg-emerald-950/60 border border-emerald-800 rounded-lg text-emerald-300 text-xs animate-in fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}
      {actionErrorMsg && (
        <div className="flex items-center gap-2 p-3 bg-red-950/60 border border-red-800 rounded-lg text-red-300 text-xs animate-in fade-in">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{actionErrorMsg}</span>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-800 overflow-x-auto pb-px">
        {[
          { id: 'overview', label: 'Overview', icon: TrendingUp },
          { id: 'plans', label: 'Plans & Tiers', icon: Sparkles },
          { id: 'usage', label: 'Pipeline Usage Ledger', icon: Layers },
          { id: 'consumption', label: 'Consumption Breakdown', icon: Clock },
          { id: 'breakdown', label: 'Software vs Cloud Cost', icon: DollarSign },
          { id: 'invoices', label: 'Invoices & Tax History', icon: FileText },
          { id: 'estimator', label: 'Cost Estimator', icon: Sliders },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                isActive
                  ? 'border-brand-500 text-brand-400 font-semibold bg-brand-500/5'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && overview && (
        <div className="space-y-6">
          {/* Top 4 KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Card 1: Active Subscription */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Plan</span>
                  <h3 className="text-lg font-bold text-white mt-1">{overview.plan_name}</h3>
                </div>
                <div className="p-2 rounded-lg bg-brand-500/10 text-brand-400">
                  <Sparkles className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-slate-400">Rate ({overview.billing_period}):</span>
                <span className="font-semibold text-white">
                  ₹{overview.billing_period === 'Annual' 
                    ? overview.annual_subscription_amount.toLocaleString() 
                    : overview.monthly_subscription_amount.toLocaleString()}
                  <span className="text-[10px] text-slate-400 ml-1">/{overview.billing_period === 'Annual' ? 'yr' : 'mo'}</span>
                </span>
              </div>
            </div>

            {/* Card 2: Consumed Runs */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Allowance Meter</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl font-bold text-white font-mono">{overview.consumed_runs.toLocaleString()}</span>
                    <span className="text-xs text-slate-400 font-mono">/ {overview.included_runs.toLocaleString()}</span>
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                  <Zap className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-3">
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${
                      consumedPct > 90 ? 'bg-red-500' : consumedPct > 75 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.max(1, consumedPct)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 font-mono">
                  <span>{consumedPct}% consumed</span>
                  <span>{overview.remaining_runs.toLocaleString()} left</span>
                </div>
              </div>
            </div>

            {/* Card 3: Estimated Current Charges */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Current Period Bill</span>
                  <h3 className="text-2xl font-bold text-white mt-1 font-mono">
                    ₹{overview.estimated_total_software_charges.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </h3>
                </div>
                <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                  <DollarSign className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-slate-400">Overages:</span>
                <span className="font-semibold text-white font-mono">₹{overview.estimated_overage_charges.toFixed(2)}</span>
              </div>
            </div>

            {/* Card 4: Next Billing Cycle */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Next Renewal</span>
                  <h3 className="text-sm font-semibold text-white mt-1">
                    {overview.next_billing_date ? new Date(overview.next_billing_date).toLocaleDateString() : 'Active Renewal'}
                  </h3>
                </div>
                <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
                  <Calendar className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-slate-400">Tenant:</span>
                <span className="font-semibold text-white truncate max-w-[130px]">{overview.tenant.name}</span>
              </div>
            </div>
          </div>

          {/* BYOC Infrastructure Clarification Banner */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 shrink-0">
                <Server className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-xs font-semibold text-white">BYOC (Bring Your Own Cloud) Operating Model</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  DataForge charges only for software orchestration and control plane execution. Your underlying AWS, Azure, or GCP compute/storage charges are billed directly by your cloud provider with zero markup.
                </p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-[11px] text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded">
                Egress / Markup: ₹0.00 (Zero)
              </span>
            </div>
          </div>

          {/* Rate Card & Activity Classification */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white">Configured Additional Run Overage Schedule</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Runs exceeding the {overview.included_runs.toLocaleString()} included monthly runs are billed on activity complexity:
                </p>
              </div>
              <span className="text-xs text-brand-400 font-mono">Currency: {overview.currency}</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-400 block">Basic Pipeline</span>
                  <span className="text-xs font-medium text-slate-300">2–5 Activities</span>
                </div>
                <div className="text-right">
                  <span className="text-base font-bold text-white font-mono">₹0.50</span>
                  <span className="text-[10px] text-slate-500 block">/ run</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-400 block">Standard Pipeline</span>
                  <span className="text-xs font-medium text-slate-300">6–15 Activities</span>
                </div>
                <div className="text-right">
                  <span className="text-base font-bold text-white font-mono">₹1.50</span>
                  <span className="text-[10px] text-slate-500 block">/ run</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-400 block">Advanced Pipeline</span>
                  <span className="text-xs font-medium text-slate-300">16–30 Activities</span>
                </div>
                <div className="text-right">
                  <span className="text-base font-bold text-white font-mono">₹3.00</span>
                  <span className="text-[10px] text-slate-500 block">/ run</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-400 block">Complex Pipeline</span>
                  <span className="text-xs font-medium text-slate-300">31+ Activities</span>
                </div>
                <div className="text-right">
                  <span className="text-base font-bold text-white font-mono">₹5.00</span>
                  <span className="text-[10px] text-slate-500 block">/ custom</span>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Live Pipeline Runs Usage Table */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">Recent Metered Pipeline Executions</h3>
                <p className="text-xs text-slate-400 mt-0.5">Live execution audit trail feeding into the monthly usage ledger.</p>
              </div>
              <button
                onClick={() => setActiveTab('usage')}
                className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1"
              >
                View Full Usage Ledger <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                    <th className="py-2.5 px-3">Run ID</th>
                    <th className="py-2.5 px-3">Pipeline</th>
                    <th className="py-2.5 px-3">Engine</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Duration</th>
                    <th className="py-2.5 px-3">Classification</th>
                    <th className="py-2.5 px-3 text-right">Billable Charge</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {recentRuns.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-500 font-sans">
                        No recent execution records found in active workspace.
                      </td>
                    </tr>
                  ) : (
                    recentRuns.map((r: any) => {
                      const acts = r.activity_runs ? r.activity_runs.length : 1;
                      let classification = 'Basic';
                      let rate = '₹0.50';
                      if (acts >= 6 && acts <= 15) { classification = 'Standard'; rate = '₹1.50'; }
                      else if (acts >= 16 && acts <= 30) { classification = 'Advanced'; rate = '₹3.00'; }
                      else if (acts > 30) { classification = 'Complex'; rate = '₹5.00'; }

                      const isBillable = r.status !== 'Cancelled';

                      return (
                        <tr key={r.id} className="hover:bg-slate-800/30 transition">
                          <td className="py-2.5 px-3 text-slate-300 truncate max-w-[120px]" title={r.id}>
                            {r.id.substring(0, 8)}...
                          </td>
                          <td className="py-2.5 px-3 text-white font-medium font-sans truncate max-w-[150px]">
                            {r.pipeline_name || r.pipeline_id?.substring(0, 8) || 'Ad-Hoc Run'}
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 border border-slate-700">
                              {r.engine || 'Copy Engine'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium ${
                              r.status === 'Completed' || r.status === 'Succeeded'
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : r.status === 'Failed'
                                ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                                : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                            }`}>
                              {r.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-400">
                            {r.duration_seconds ? `${r.duration_seconds.toFixed(1)}s` : '—'}
                          </td>
                          <td className="py-2.5 px-3 font-sans text-slate-300">
                            {classification} ({acts} act)
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <span className={isBillable ? 'text-white font-bold' : 'text-slate-500 line-through'}>
                              {isBillable ? (overview.remaining_runs > 0 ? 'Included' : rate) : 'Non-billable'}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: PLANS & TIERS */}
      {activeTab === 'plans' && (
        <div className="space-y-6">
          {/* Billing Period Selector */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-white">Commercial Subscription Tiers</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Scale predictably with included pipeline runs, high-throughput engines, and SLA guarantees.
              </p>
            </div>

            <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-lg border border-slate-800 self-start sm:self-auto">
              <button
                onClick={() => setBillingPeriodToggle('Monthly')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                  billingPeriodToggle === 'Monthly'
                    ? 'bg-brand-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Monthly Billing
              </button>
              <button
                onClick={() => setBillingPeriodToggle('Annual')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${
                  billingPeriodToggle === 'Annual'
                    ? 'bg-brand-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>Annual Billing</span>
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30">
                  Save 17%
                </span>
              </button>
            </div>
          </div>

          {/* Plan Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map((p) => {
              const pricing = p.active_pricing;
              const isCurrent = overview?.plan_name.toLowerCase() === p.name.toLowerCase();
              const price = billingPeriodToggle === 'Annual' 
                ? (pricing?.annual_base_price || 0) / 12 
                : (pricing?.monthly_base_price || 0);

              const isPro = p.plan_code === 'professional';

              return (
                <div 
                  key={p.id}
                  className={`p-6 rounded-2xl flex flex-col justify-between transition-all relative ${
                    isPro 
                      ? 'bg-gradient-to-b from-slate-900 to-brand-950/20 border-2 border-brand-500 shadow-xl shadow-brand-950/40' 
                      : 'bg-slate-900 border border-slate-800'
                  }`}
                >
                  {isPro && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-brand-500 text-white shadow-md">
                      Most Popular
                    </div>
                  )}

                  <div>
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-bold text-white">{p.name}</h3>
                      {isCurrent && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          Active Plan
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-2 min-h-[36px]">{p.description}</p>

                    <div className="mt-5 pb-5 border-b border-slate-800">
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-extrabold text-white font-mono">
                          ₹{Math.round(price).toLocaleString()}
                        </span>
                        <span className="text-xs text-slate-400">/month</span>
                      </div>
                      <span className="text-[10px] text-slate-500 block mt-1">
                        {billingPeriodToggle === 'Annual' 
                          ? `Billed annually at ₹${pricing?.annual_base_price?.toLocaleString()}/yr` 
                          : 'Billed monthly, cancel anytime'}
                      </span>
                    </div>

                    {/* Features List */}
                    <div className="mt-5 space-y-3 text-xs">
                      <div className="flex items-center gap-2.5 text-slate-200">
                        <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        <span className="font-semibold text-white">
                          {pricing?.included_pipeline_runs.toLocaleString()} Included Runs / mo
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 text-slate-300">
                        <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        <span>Copy Engine: <strong className="text-white">{p.features.copy_engine || 'Standard'}</strong></span>
                      </div>
                      <div className="flex items-center gap-2.5 text-slate-300">
                        {p.features.spark_engine ? (
                          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="h-4 w-4 text-slate-600 shrink-0" />
                        )}
                        <span className={p.features.spark_engine ? 'text-white' : 'text-slate-500'}>
                          Managed Spark Engine
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 text-slate-300">
                        {p.features.sql_pushdown ? (
                          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="h-4 w-4 text-slate-600 shrink-0" />
                        )}
                        <span className={p.features.sql_pushdown ? 'text-white' : 'text-slate-500'}>
                          In-Database SQL Pushdown
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 text-slate-300">
                        <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        <span>Data Quality: <strong className="text-white">{p.features.data_quality || 'Basic'}</strong></span>
                      </div>
                      <div className="flex items-center gap-2.5 text-slate-300">
                        {p.features.self_hosted_runtime ? (
                          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="h-4 w-4 text-slate-600 shrink-0" />
                        )}
                        <span className={p.features.self_hosted_runtime ? 'text-white font-semibold' : 'text-slate-500'}>
                          Self-Hosted Integration Runtime
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 text-slate-300">
                        <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                        <span>Support: <strong className="text-white">{p.features.support_tier || 'Standard'}</strong></span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 pt-4">
                    <button
                      disabled={isCurrent || isUpdatingSub}
                      onClick={() => handlePlanSwitch(p.id, billingPeriodToggle)}
                      className={`w-full py-2.5 px-4 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2 ${
                        isCurrent
                          ? 'bg-slate-800 text-slate-400 border border-slate-700 cursor-not-allowed'
                          : isPro
                          ? 'bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-600/30'
                          : 'bg-slate-800 hover:bg-slate-700 text-white border border-slate-700'
                      }`}
                    >
                      {isCurrent ? (
                        <>
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                          Current Selected Plan
                        </>
                      ) : (
                        <>
                          Switch to {p.name}
                          <ArrowUpRight className="h-4 w-4" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Enterprise Custom Banner */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-brand-950/30 to-slate-900 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Building className="h-5 w-5 text-brand-400" />
                <h4 className="text-base font-bold text-white">Need Custom Volume Licensing or Custom Connectors?</h4>
              </div>
              <p className="text-xs text-slate-400 max-w-2xl">
                For organizations with over 1,000,000 pipeline executions/month, hybrid air-gapped private clusters, or custom compliance auditing requirements, we offer tailored Enterprise Agreements.
              </p>
            </div>
            <a
              href="mailto:enterprise@dataflow.enterprise"
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 whitespace-nowrap transition flex items-center gap-2 shrink-0"
            >
              Contact Enterprise Sales
              <ArrowUpRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      )}

      {/* TAB 3: PIPELINE USAGE LEDGER */}
      {activeTab === 'usage' && (
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-white">Immutable Pipeline Usage Ledger</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Every pipeline run generates an idempotent usage entry with complexity classification and billable status.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => alert('Exporting usage ledger as CSV...')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
              >
                <Download className="h-3.5 w-3.5" />
                Export CSV
              </button>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-3 p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-medium">Engine:</span>
              <select
                value={filterEngine}
                onChange={(e) => setFilterEngine(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1 text-xs outline-none focus:border-brand-500"
              >
                <option value="ALL">All Engines</option>
                <option value="CopyEngine">CopyEngine</option>
                <option value="SparkEngine">SparkEngine</option>
                <option value="SqlPushdownEngine">SqlPushdownEngine</option>
                <option value="Hybrid">Hybrid</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-medium">Classification:</span>
              <select
                value={filterClassification}
                onChange={(e) => setFilterClassification(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1 text-xs outline-none focus:border-brand-500"
              >
                <option value="ALL">All Tiers</option>
                <option value="Basic">Basic (2–5 act)</option>
                <option value="Standard">Standard (6–15 act)</option>
                <option value="Advanced">Advanced (16–30 act)</option>
                <option value="Complex">Complex (31+ act)</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-medium">Billability:</span>
              <select
                value={filterBillable}
                onChange={(e) => setFilterBillable(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1 text-xs outline-none focus:border-brand-500"
              >
                <option value="ALL">All Runs</option>
                <option value="BILLABLE">Billable Only</option>
                <option value="NON_BILLABLE">Non-Billable Only</option>
              </select>
            </div>

            {(filterEngine !== 'ALL' || filterClassification !== 'ALL' || filterBillable !== 'ALL') && (
              <button
                onClick={() => {
                  setFilterEngine('ALL');
                  setFilterClassification('ALL');
                  setFilterBillable('ALL');
                }}
                className="text-xs text-brand-400 hover:text-brand-300 ml-auto"
              >
                Clear Filters
              </button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Run ID</th>
                  <th className="py-2.5 px-3">Pipeline</th>
                  <th className="py-2.5 px-3">Engine</th>
                  <th className="py-2.5 px-3">Activities</th>
                  <th className="py-2.5 px-3">Tier</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Billable</th>
                  <th className="py-2.5 px-3 text-right">Charge</th>
                  <th className="py-2.5 px-3 text-right">Admin Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {(() => {
                  const itemsToRender = usageLedger.length > 0 ? usageLedger.filter((item) => {
                    if (filterEngine !== 'ALL' && item.execution_engine !== filterEngine) return false;
                    if (filterClassification !== 'ALL' && item.classification !== filterClassification) return false;
                    if (filterBillable === 'BILLABLE' && !item.is_billable) return false;
                    if (filterBillable === 'NON_BILLABLE' && item.is_billable) return false;
                    return true;
                  }) : recentRuns.map((r: any) => {
                    const acts = r.activity_runs ? r.activity_runs.length : 1;
                    let classification: any = 'Basic';
                    let rate = 0.50;
                    if (acts >= 6 && acts <= 15) { classification = 'Standard'; rate = 1.50; }
                    else if (acts >= 16 && acts <= 30) { classification = 'Advanced'; rate = 3.00; }
                    else if (acts > 30) { classification = 'Complex'; rate = 5.00; }
                    return {
                      id: r.id,
                      pipeline_run_id: r.id,
                      pipeline_name: r.pipeline_name || r.pipeline_id?.substring(0, 8) || 'Ad-Hoc',
                      execution_engine: r.engine || 'CopyEngine',
                      activity_count: acts,
                      classification: classification,
                      execution_status: r.status,
                      started_at: r.started_at,
                      is_billable: r.status !== 'Cancelled',
                      calculated_charge: r.status !== 'Cancelled' ? rate : 0.0,
                      non_billable_reason: r.status === 'Cancelled' ? 'UserCancelled' : undefined
                    };
                  });

                  if (itemsToRender.length === 0) {
                    return (
                      <tr>
                        <td colSpan={10} className="py-8 text-center text-slate-500 font-sans">
                          No matching usage entries found for the selected filters.
                        </td>
                      </tr>
                    );
                  }

                  return itemsToRender.map((entry: any) => (
                    <tr key={entry.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {entry.started_at ? new Date(entry.started_at).toLocaleString() : 'Recent'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 truncate max-w-[100px]" title={entry.pipeline_run_id}>
                        {entry.pipeline_run_id.substring(0, 8)}...
                      </td>
                      <td className="py-2.5 px-3 text-white font-sans font-medium truncate max-w-[130px]">
                        {entry.pipeline_name}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {entry.execution_engine}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 text-center">
                        {entry.activity_count}
                      </td>
                      <td className="py-2.5 px-3 font-sans text-slate-300">
                        {entry.classification}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium ${
                          entry.execution_status === 'Completed' || entry.execution_status === 'Succeeded'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                          {entry.execution_status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-sans">
                        {entry.is_billable ? (
                          <span className="text-emerald-400 flex items-center gap-1 text-[11px]">
                            <CheckCircle2 className="h-3 w-3" /> Yes
                          </span>
                        ) : (
                          <span className="text-slate-500 flex items-center gap-1 text-[11px]" title={entry.non_billable_reason || 'Non-billable'}>
                            <XCircle className="h-3 w-3" /> No
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={entry.is_billable ? 'text-white font-bold' : 'text-slate-500 line-through'}>
                          ₹{Number(entry.calculated_charge).toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-sans">
                        {usageLedger.length > 0 && entry.id ? (
                          <button
                            onClick={() => handleOverrideBillability(entry.id, entry.is_billable)}
                            className="px-2 py-1 rounded text-[10px] text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
                          >
                            {entry.is_billable ? 'Waive' : 'Bill'}
                          </button>
                        ) : (
                          <span className="text-slate-600 text-[10px]">—</span>
                        )}
                      </td>
                    </tr>
                  ));
                })()}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: CONSUMPTION BREAKDOWN */}
      {activeTab === 'consumption' && (
        <div className="space-y-6">
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
            <h3 className="text-sm font-bold text-white">Engine-Wise Execution Distribution</h3>
            <p className="text-xs text-slate-400 mt-0.5">ADF-Parity consumption breakdown across DataForge compute paradigms.</p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-5">
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">Parallel Copy Engine</span>
                  <span className="p-1.5 rounded bg-blue-500/10 text-blue-400"><Server className="h-4 w-4" /></span>
                </div>
                <div className="mt-3">
                  <span className="text-2xl font-bold text-white font-mono">{recentRuns.length}</span>
                  <span className="text-xs text-slate-400 block mt-0.5">Streaming pipeline runs</span>
                </div>
                <div className="mt-3 text-[11px] text-emerald-400 flex items-center gap-1 font-mono">
                  <span>Bounded memory: &le;64 MB/partition</span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">Distributed Spark Engine</span>
                  <span className="p-1.5 rounded bg-purple-500/10 text-purple-400"><Zap className="h-4 w-4" /></span>
                </div>
                <div className="mt-3">
                  <span className="text-2xl font-bold text-white font-mono">0</span>
                  <span className="text-xs text-slate-400 block mt-0.5">Heavy ETL worker node-hours</span>
                </div>
                <div className="mt-3 text-[11px] text-slate-400 font-mono">
                  <span>Rate: ₹45.00 / node-hour</span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">In-DB SQL Pushdown</span>
                  <span className="p-1.5 rounded bg-emerald-500/10 text-emerald-400"><ShieldCheck className="h-4 w-4" /></span>
                </div>
                <div className="mt-3">
                  <span className="text-2xl font-bold text-white font-mono">0</span>
                  <span className="text-xs text-slate-400 block mt-0.5">Zero-egress warehouse transforms</span>
                </div>
                <div className="mt-3 text-[11px] text-emerald-400 font-mono">
                  <span>Network Egress: ₹0.00</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: SOFTWARE VS CLOUD BREAKDOWN */}
      {activeTab === 'breakdown' && (
        <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <DollarSign className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Financial Separation: Software vs Infrastructure</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Strict separation between DataForge software fees and customer BYOC cloud infrastructure costs.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
            <div className="p-5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-brand-400" />
                DataForge Platform Invoicing
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Platform Subscription ({overview?.plan_name})</span>
                  <span className="text-white font-mono">₹{overview?.monthly_subscription_amount.toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Additional Pipeline Run Surcharges</span>
                  <span className="text-white font-mono">₹{overview?.estimated_overage_charges.toFixed(2)}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Managed Spark Worker Execution</span>
                  <span className="text-white font-mono">₹{overview?.estimated_spark_compute_charges.toFixed(2)}</span>
                </div>
                <div className="flex justify-between py-2 pt-3 font-semibold text-white">
                  <span>Total DataForge Software Due</span>
                  <span className="font-mono text-brand-400 text-sm">
                    ₹{overview?.estimated_total_software_charges.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                Customer Cloud Provider (BYOC)
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Azure Blob / AWS S3 Storage</span>
                  <span className="text-slate-300 font-mono">Billed directly by cloud provider</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">VM Compute / Self-Hosted Agent Nodes</span>
                  <span className="text-slate-300 font-mono">Billed directly by cloud provider</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Warehouse Compute (Snowflake / BigQuery)</span>
                  <span className="text-slate-300 font-mono">Billed directly by cloud provider</span>
                </div>
                <div className="flex justify-between py-2 pt-3 font-semibold text-emerald-400">
                  <span>DataForge Cloud Markup</span>
                  <span className="font-mono text-sm">₹0.00 (0% Markup)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: INVOICES & STATEMENTS */}
      {activeTab === 'invoices' && (
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white">Tax Invoices & Billing Statements</h3>
              <p className="text-xs text-slate-400 mt-0.5">Download verifiable GST / VAT compliance tax invoices and receipts.</p>
            </div>
            <span className="text-xs font-mono text-slate-400">GST: 18.0% applicable</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                  <th className="py-2.5 px-3">Invoice Number</th>
                  <th className="py-2.5 px-3">Billing Period</th>
                  <th className="py-2.5 px-3">Subscription</th>
                  <th className="py-2.5 px-3">Usage Surcharges</th>
                  <th className="py-2.5 px-3">GST (18%)</th>
                  <th className="py-2.5 px-3">Total Amount</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                <tr className="hover:bg-slate-800/30 transition">
                  <td className="py-2.5 px-3 text-white font-medium">INV-2026-001</td>
                  <td className="py-2.5 px-3 text-slate-300 font-sans">Current Active Period</td>
                  <td className="py-2.5 px-3 text-slate-300">₹{overview?.monthly_subscription_amount.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-slate-300">₹{overview?.estimated_overage_charges.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-slate-300">
                    ₹{((overview?.estimated_total_software_charges || 0) * 0.18).toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-brand-400 font-bold">
                    ₹{((overview?.estimated_total_software_charges || 0) * 1.18).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Paid / Active
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-sans">
                    <button 
                      onClick={() => alert('Generating compliance PDF statement...')}
                      className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 ml-auto"
                    >
                      <Download className="h-3 w-3" /> PDF
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 7: COST ESTIMATOR */}
      {activeTab === 'estimator' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Inputs Section */}
          <div className="lg:col-span-7 p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-6">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sliders className="h-4 w-4 text-brand-400" />
                DataForge Interactive Sizing & Cost Calculator
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Model your workload requirements to calculate exact monthly subscription costs, overage surcharges, and ADF migration savings.
              </p>
            </div>

            {/* Slider 1: Expected Monthly Runs */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-200">Expected Monthly Pipeline Executions</label>
                <span className="text-sm font-bold text-brand-400 font-mono">{estRuns.toLocaleString()} runs</span>
              </div>
              <input
                type="range"
                min={1000}
                max={200000}
                step={1000}
                value={estRuns}
                onChange={(e) => setEstRuns(Number(e.target.value))}
                className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>1,000</span>
                <span>50,000 (Pro Included)</span>
                <span>200,000+</span>
              </div>
            </div>

            {/* Slider 2: Average Activities per Pipeline */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-200">Average Activities per Pipeline</label>
                <span className="text-sm font-bold text-brand-400 font-mono">{estActivities} activities</span>
              </div>
              <input
                type="range"
                min={2}
                max={40}
                step={1}
                value={estActivities}
                onChange={(e) => setEstActivities(Number(e.target.value))}
                className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>2 (Basic ₹0.50)</span>
                <span>8 (Standard ₹1.50)</span>
                <span>20 (Adv ₹3.00)</span>
                <span>40 (Complex ₹5.00)</span>
              </div>
            </div>

            {/* Slider 3: Spark Worker Node-Hours */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-200">Managed Spark Worker Node-Hours</label>
                <span className="text-sm font-bold text-brand-400 font-mono">{estSparkHours} node-hrs/mo</span>
              </div>
              <input
                type="range"
                min={0}
                max={200}
                step={5}
                value={estSparkHours}
                onChange={(e) => setEstSparkHours(Number(e.target.value))}
                className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>0 (Pure Copy Engine)</span>
                <span>50 hrs</span>
                <span>200 hrs</span>
              </div>
            </div>

            {/* Toggle Billing Frequency */}
            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs text-slate-300 font-medium">Billing Commitment:</span>
              <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-lg border border-slate-800">
                <button
                  onClick={() => setEstPeriod('Monthly')}
                  className={`px-3 py-1 rounded text-xs transition ${
                    estPeriod === 'Monthly' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400'
                  }`}
                >
                  Monthly
                </button>
                <button
                  onClick={() => setEstPeriod('Annual')}
                  className={`px-3 py-1 rounded text-xs transition ${
                    estPeriod === 'Annual' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400'
                  }`}
                >
                  Annual (-17%)
                </button>
              </div>
            </div>
          </div>

          {/* Results Summary Section */}
          <div className="lg:col-span-5 p-6 rounded-2xl bg-gradient-to-b from-slate-900 to-brand-950/30 border border-slate-800 flex flex-col justify-between space-y-6">
            <div>
              <span className="text-[11px] font-semibold text-brand-400 uppercase tracking-wider block">
                Workload Recommendation
              </span>
              <h3 className="text-xl font-bold text-white capitalize mt-1">
                {estResult.recPlan} Plan
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Includes {estResult.includedRuns.toLocaleString()} monthly pipeline executions.
              </p>

              <div className="mt-6 space-y-3 text-xs">
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Base Subscription</span>
                  <span className="text-white font-mono font-semibold">₹{Math.round(estResult.basePrice).toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Included Executions</span>
                  <span className="text-emerald-400 font-mono">{estResult.includedRuns.toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Estimated Overage ({estResult.overageRuns.toLocaleString()} runs)</span>
                  <span className="text-white font-mono font-semibold">₹{Math.round(estResult.overageCost).toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Spark Compute ({estSparkHours} hrs)</span>
                  <span className="text-white font-mono font-semibold">₹{Math.round(estResult.sparkCost).toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-3 font-bold text-white text-base">
                  <span>Total Estimated Cost</span>
                  <span className="text-brand-400 font-mono">₹{Math.round(estResult.totalMonthly).toLocaleString()}<span className="text-xs text-slate-400">/mo</span></span>
                </div>
              </div>

              {/* ADF Comparison Widget */}
              <div className="mt-5 p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Azure Data Factory Equivalent:</span>
                  <span className="text-slate-300 font-mono line-through">₹{Math.round(estResult.adfEquivalent).toLocaleString()}/mo</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Estimated Savings vs ADF:
                  </span>
                  <span className="text-emerald-400 font-bold font-mono text-sm">~{estResult.savingsPercent}% lower</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                const targetPlan = plans.find(p => p.plan_code === estResult.recPlan);
                if (targetPlan) {
                  handlePlanSwitch(targetPlan.id, estPeriod);
                }
              }}
              disabled={isUpdatingSub}
              className="w-full py-3 rounded-xl text-xs font-bold text-white bg-brand-600 hover:bg-brand-500 shadow-lg shadow-brand-600/30 transition flex items-center justify-center gap-2"
            >
              <Sparkles className="h-4 w-4" />
              Subscribe to {estResult.recPlan.toUpperCase()} Plan
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
