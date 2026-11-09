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
  ChevronLeft,
  Download,
  FileText,
  Building,
  Info,
  Search,
  Filter,
  X,
  Copy,
  ExternalLink,
  BarChart3,
  PieChart,
  Bell,
  Plus,
  Trash2,
  Edit3,
  ShieldAlert,
  Target
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  AreaChart,
  Area
} from 'recharts';
import { 
  BillingOverview, 
  SubscriptionPlan, 
  CustomerSubscription,
  PipelineUsageLedgerEntry,
  ConsumptionSummary,
  BillingInvoice,
  InvoiceLineItem,
  PaymentRecord,
  CostEstimateResult,
  PlanComparisonItem,
  BudgetStatus,
  BudgetAlertRecipient,
  BudgetAlertRecord,
  BudgetEvaluationResult,
  BillingAuditLogEntry,
  PricingConfigVersion
} from '../types';

export const BillingPage: React.FC = () => {
  const { activeWorkspace } = useAppStore();
  const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'usage' | 'consumption' | 'breakdown' | 'invoices' | 'estimator' | 'budgets' | 'admin'>('overview');
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [recentRuns, setRecentRuns] = useState<any[]>([]);
  const [usageLedger, setUsageLedger] = useState<PipelineUsageLedgerEntry[]>([]);
  const [consumptionSummary, setConsumptionSummary] = useState<ConsumptionSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUpdatingSub, setIsUpdatingSub] = useState<boolean>(false);
  const [billingPeriodToggle, setBillingPeriodToggle] = useState<'Monthly' | 'Annual'>('Monthly');
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null);

  // Budget Management & Alerts State
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [isLoadingBudgets, setIsLoadingBudgets] = useState<boolean>(false);
  const [isEvaluatingBudgets, setIsEvaluatingBudgets] = useState<boolean>(false);
  const [isBudgetModalOpen, setIsBudgetModalOpen] = useState<boolean>(false);
  const [editingBudget, setEditingBudget] = useState<BudgetStatus | null>(null);
  const [budgetFormName, setBudgetFormName] = useState<string>('');
  const [budgetFormSpendLimit, setBudgetFormSpendLimit] = useState<string>('25000');
  const [budgetFormRunLimit, setBudgetFormRunLimit] = useState<string>('10000');
  const [budgetFormHardLimit, setBudgetFormHardLimit] = useState<boolean>(false);
  const [budgetFormThresholds, setBudgetFormThresholds] = useState<number[]>([50, 75, 90, 100]);
  const [budgetFormRecipients, setBudgetFormRecipients] = useState<BudgetAlertRecipient[]>([]);
  const [recipientChannel, setRecipientChannel] = useState<'email' | 'slack' | 'webhook'>('email');
  const [recipientTarget, setRecipientTarget] = useState<string>('');
  const [isSavingBudget, setIsSavingBudget] = useState<boolean>(false);

  // Admin Pricing & Audit Console State
  const [adminPlans, setAdminPlans] = useState<SubscriptionPlan[]>([]);
  const [auditLogs, setAuditLogs] = useState<BillingAuditLogEntry[]>([]);
  const [isLoadingAdmin, setIsLoadingAdmin] = useState<boolean>(false);
  const [isPublishModalOpen, setIsPublishModalOpen] = useState<boolean>(false);
  const [selectedPlanForVersion, setSelectedPlanForVersion] = useState<SubscriptionPlan | null>(null);
  const [pubMonthlyPrice, setPubMonthlyPrice] = useState<string>('9999');
  const [pubAnnualPrice, setPubAnnualPrice] = useState<string>('99990');
  const [pubIncludedRuns, setPubIncludedRuns] = useState<string>('10000');
  const [pubBasicRate, setPubBasicRate] = useState<string>('0.50');
  const [pubStandardRate, setPubStandardRate] = useState<string>('1.50');
  const [pubAdvancedRate, setPubAdvancedRate] = useState<string>('3.00');
  const [pubComplexRate, setPubComplexRate] = useState<string>('5.00');
  const [pubSparkRate, setPubSparkRate] = useState<string>('45.0');
  const [pubCurrency, setPubCurrency] = useState<string>('INR');
  const [pubJustification, setPubJustification] = useState<string>('');
  const [isPublishingVersion, setIsPublishingVersion] = useState<boolean>(false);

  // Custom Enterprise Agreement State
  const [isCustomAgreementModalOpen, setIsCustomAgreementModalOpen] = useState<boolean>(false);
  const [customTenantId, setCustomTenantId] = useState<string>('');
  const [customPlanName, setCustomPlanName] = useState<string>('Enterprise Custom Volume Agreement');
  const [customMonthlyPrice, setCustomMonthlyPrice] = useState<string>('150000');
  const [customAnnualPrice, setCustomAnnualPrice] = useState<string>('1500000');
  const [customIncludedRuns, setCustomIncludedRuns] = useState<string>('750000');
  const [customBasicRate, setCustomBasicRate] = useState<string>('0.30');
  const [customStandardRate, setCustomStandardRate] = useState<string>('1.00');
  const [customAdvancedRate, setCustomAdvancedRate] = useState<string>('2.00');
  const [customComplexRate, setCustomComplexRate] = useState<string>('3.50');
  const [customSparkRate, setCustomSparkRate] = useState<string>('30.0');
  const [customNotes, setCustomNotes] = useState<string>('Negotiated high-scale enterprise volume licensing');
  const [customJustification, setCustomJustification] = useState<string>('');
  const [isSavingCustomAgreement, setIsSavingCustomAgreement] = useState<boolean>(false);

  // Manual Adjustment State
  const [isAdjustmentModalOpen, setIsAdjustmentModalOpen] = useState<boolean>(false);
  const [adjInvoiceId, setAdjInvoiceId] = useState<string>('');
  const [adjAmount, setAdjAmount] = useState<string>('');
  const [adjType, setAdjType] = useState<string>('GoodwillSLA');
  const [adjDesc, setAdjDesc] = useState<string>('SLA Incident goodwill credit adjustment');
  const [adjJustification, setAdjJustification] = useState<string>('');
  const [isApplyingAdjustment, setIsApplyingAdjustment] = useState<boolean>(false);

  // Audit Diff Viewer Drawer
  const [selectedAuditLogForDiff, setSelectedAuditLogForDiff] = useState<BillingAuditLogEntry | null>(null);

  // Drawer state for run details
  const [selectedRunForDrawer, setSelectedRunForDrawer] = useState<PipelineUsageLedgerEntry | null>(null);

  // Invoices & Payments State
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<BillingInvoice | null>(null);
  const [isGeneratingInvoice, setIsGeneratingInvoice] = useState<boolean>(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState<boolean>(false);
  const [paymentAmount, setPaymentAmount] = useState<string>('');
  const [paymentRef, setPaymentRef] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<string>('BankTransfer');
  const [paymentNotes, setPaymentNotes] = useState<string>('');
  const [isRecordingPayment, setIsRecordingPayment] = useState<boolean>(false);

  // Filters for Usage Ledger
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterEngine, setFilterEngine] = useState<string>('ALL');
  const [filterClassification, setFilterClassification] = useState<string>('ALL');
  const [filterBillable, setFilterBillable] = useState<string>('ALL');
  const [filterDateRange, setFilterDateRange] = useState<'all' | 'today' | '7d' | '30d'>('all');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  // Consumption Visualizer view mode
  const [consumptionChartMode, setConsumptionChartMode] = useState<'tiers' | 'engines'>('tiers');

  // Estimator State
  const [estPipelines, setEstPipelines] = useState<number>(10);
  const [estRuns, setEstRuns] = useState<number>(35000);
  const [estActivities, setEstActivities] = useState<number>(8);
  const [copyEnginePct, setCopyEnginePct] = useState<number>(60);
  const [sparkEnginePct, setSparkEnginePct] = useState<number>(20);
  const [sqlPushdownPct, setSqlPushdownPct] = useState<number>(20);
  const [dataVolumeGB, setDataVolumeGB] = useState<number>(500);
  const [runtimeHours, setRuntimeHours] = useState<number>(100);
  const [deploymentModel, setDeploymentModel] = useState<'BYOC' | 'SaaS'>('BYOC');
  const [estPeriod, setEstPeriod] = useState<'Monthly' | 'Annual'>('Monthly');

  const fetchData = async () => {
    setIsLoading(true);
    setActionErrorMsg(null);
    try {
      const [overviewRes, plansRes, runsRes, usageRes, summaryRes, invoicesRes, budgetsRes, adminPlansRes, auditLogsRes] = await Promise.all([
        api.get('/billing/overview'),
        api.get('/billing/plans'),
        api.get('/runs?limit=15').catch(() => ({ data: [] })),
        api.get('/billing/usage?limit=100').catch(() => ({ data: [] })),
        api.get('/billing/usage/summary').catch(() => ({ data: null })),
        api.get('/billing/invoices').catch(() => ({ data: [] })),
        api.get(`/billing/budgets${activeWorkspace ? `?workspace_id=${activeWorkspace.id}` : ''}`).catch(() => ({ data: [] })),
        api.get('/billing/admin/plans').catch(() => ({ data: [] })),
        api.get('/billing/admin/audit-logs').catch(() => ({ data: [] }))
      ]);

      setOverview(overviewRes.data);
      setPlans(plansRes.data);
      setRecentRuns(runsRes.data || []);
      setUsageLedger(usageRes.data || []);
      setConsumptionSummary(summaryRes.data);
      setInvoices(invoicesRes.data || []);
      setBudgets(budgetsRes.data || []);
      setAdminPlans(adminPlansRes.data || []);
      setAuditLogs(auditLogsRes.data || []);
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
      if (selectedRunForDrawer && selectedRunForDrawer.id === ledgerId) {
        setSelectedRunForDrawer(prev => prev ? { ...prev, is_billable: nextBillable, non_billable_reason: nextBillable ? undefined : reason } : null);
      }
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to override billability', err);
      setActionErrorMsg(err.response?.data?.detail || 'Billability override failed.');
    }
  };

  const handleRecalculateRating = async () => {
    try {
      await api.post('/billing/usage/recalculate');
      setActionSuccessMsg('Usage rating & rollups recalculated successfully.');
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to recalculate rating', err);
      setActionErrorMsg(err.response?.data?.detail || 'Recalculation failed.');
    }
  };

  const handleExportCSV = () => {
    const recordsToExport = usageLedger.length > 0 ? usageLedger : recentRuns.map((r: any) => ({
      id: r.id,
      pipeline_run_id: r.id,
      pipeline_name: r.pipeline_name || r.pipeline_id?.substring(0, 8) || 'Ad-Hoc',
      execution_engine: r.engine || 'CopyEngine',
      activity_count: r.activity_runs ? r.activity_runs.length : 1,
      classification: 'Standard',
      execution_status: r.status,
      is_billable: r.status !== 'Cancelled',
      calculated_charge: r.status !== 'Cancelled' ? 1.50 : 0.0,
      started_at: r.started_at
    }));

    if (recordsToExport.length === 0) {
      alert('No usage records available to export.');
      return;
    }

    const headers = [
      'Record ID', 'Run ID', 'Pipeline Name', 'Execution Engine', 
      'Activities', 'Classification', 'Status', 'Is Billable', 
      'Calculated Charge (INR)', 'Timestamp'
    ];
    const rows = recordsToExport.map((r: any) => [
      r.id,
      r.pipeline_run_id,
      `"${(r.pipeline_name || '').replace(/"/g, '""')}"`,
      r.execution_engine,
      r.activity_count,
      r.classification,
      r.execution_status,
      r.is_billable ? 'Yes' : 'No',
      r.calculated_charge,
      r.started_at
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `dataforge_usage_ledger_${overview?.tenant?.name || 'export'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleExportJSON = () => {
    if (!consumptionSummary) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(consumptionSummary, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `dataforge_consumption_summary_${consumptionSummary.period_key}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleDownloadInvoicePDF = async (invoiceId: string, invoiceNumber: string) => {
    try {
      const response = await api.get(`/billing/invoices/${invoiceId}/download`, {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${invoiceNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Failed to download invoice PDF', err);
      setActionErrorMsg('Failed to download PDF statement.');
    }
  };

  const handleGenerateInvoice = async () => {
    setIsGeneratingInvoice(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      const res = await api.post('/billing/invoices/generate', {});
      setActionSuccessMsg(`Invoice ${res.data.invoice_number} generated successfully.`);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to generate invoice', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to generate invoice.');
    } finally {
      setIsGeneratingInvoice(false);
    }
  };

  const handleOpenInvoiceDetail = async (inv: BillingInvoice) => {
    try {
      const res = await api.get(`/billing/invoices/${inv.id}`);
      setSelectedInvoice(res.data);
    } catch (err: any) {
      setSelectedInvoice(inv);
    }
  };

  const handleOpenPaymentModal = (inv: BillingInvoice) => {
    setSelectedInvoice(inv);
    setPaymentAmount(inv.total_amount.toString());
    setPaymentRef(`UTR-${Math.random().toString(36).substring(2, 8).toUpperCase()}`);
    setPaymentMethod('BankTransfer');
    setPaymentNotes('Corporate wire transfer via NetBanking');
    setIsPaymentModalOpen(true);
  };

  const handleRecordPayment = async () => {
    if (!selectedInvoice) return;
    setIsRecordingPayment(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      await api.post(`/billing/invoices/${selectedInvoice.id}/payments`, {
        amount: parseFloat(paymentAmount),
        payment_reference: paymentRef,
        payment_method: paymentMethod,
        notes: paymentNotes
      });
      setActionSuccessMsg(`Payment of ₹${parseFloat(paymentAmount).toLocaleString()} recorded successfully.`);
      setIsPaymentModalOpen(false);
      await fetchData();
      if (selectedInvoice) {
        const updated = await api.get(`/billing/invoices/${selectedInvoice.id}`);
        setSelectedInvoice(updated.data);
      }
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to record payment', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to record payment.');
    } finally {
      setIsRecordingPayment(false);
    }
  };

  const handleOpenCreateBudgetModal = () => {
    setEditingBudget(null);
    setBudgetFormName('Production Monthly Spend Cap');
    setBudgetFormSpendLimit('25000');
    setBudgetFormRunLimit('10000');
    setBudgetFormHardLimit(false);
    setBudgetFormThresholds([50, 75, 90, 100]);
    setBudgetFormRecipients([{ channel: 'email', target: 'finops@dataforge.test' }]);
    setRecipientChannel('email');
    setRecipientTarget('');
    setIsBudgetModalOpen(true);
  };

  const handleOpenEditBudgetModal = (b: BudgetStatus) => {
    setEditingBudget(b);
    setBudgetFormName(b.name);
    setBudgetFormSpendLimit(b.monthly_limit_amount.toString());
    setBudgetFormRunLimit(b.monthly_run_limit.toString());
    setBudgetFormHardLimit(b.enforce_hard_limit);
    setBudgetFormThresholds(b.threshold_percents || [50, 75, 90, 100]);
    setBudgetFormRecipients(b.alert_recipients || []);
    setRecipientChannel('email');
    setRecipientTarget('');
    setIsBudgetModalOpen(true);
  };

  const handleAddRecipient = () => {
    if (!recipientTarget.trim()) return;
    setBudgetFormRecipients([...budgetFormRecipients, { channel: recipientChannel, target: recipientTarget.trim() }]);
    setRecipientTarget('');
  };

  const handleRemoveRecipient = (index: number) => {
    setBudgetFormRecipients(budgetFormRecipients.filter((_, idx) => idx !== index));
  };

  const handleToggleThreshold = (pct: number) => {
    if (budgetFormThresholds.includes(pct)) {
      setBudgetFormThresholds(budgetFormThresholds.filter(p => p !== pct));
    } else {
      setBudgetFormThresholds([...budgetFormThresholds, pct].sort((a, b) => a - b));
    }
  };

  const handleSaveBudget = async () => {
    if (!budgetFormName.trim()) {
      setActionErrorMsg('Budget name is required.');
      return;
    }
    setIsSavingBudget(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      if (editingBudget) {
        await api.put(`/billing/budgets/${editingBudget.id}`, {
          name: budgetFormName,
          monthly_limit_amount: parseFloat(budgetFormSpendLimit) || 0.0,
          monthly_run_limit: parseInt(budgetFormRunLimit) || 0,
          enforce_hard_limit: budgetFormHardLimit,
          threshold_percents: budgetFormThresholds,
          alert_recipients: budgetFormRecipients
        });
        setActionSuccessMsg(`Budget policy '${budgetFormName}' updated successfully.`);
      } else {
        await api.post(`/billing/budgets${activeWorkspace ? `?workspace_id=${activeWorkspace.id}` : ''}`, {
          name: budgetFormName,
          period_type: 'Monthly',
          monthly_limit_amount: parseFloat(budgetFormSpendLimit) || 0.0,
          monthly_run_limit: parseInt(budgetFormRunLimit) || 0,
          enforce_hard_limit: budgetFormHardLimit,
          threshold_percents: budgetFormThresholds,
          alert_recipients: budgetFormRecipients,
          workspace_id: activeWorkspace?.id
        });
        setActionSuccessMsg(`Budget policy '${budgetFormName}' created successfully.`);
      }
      setIsBudgetModalOpen(false);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to save budget', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to save budget configuration.');
    } finally {
      setIsSavingBudget(false);
    }
  };

  const handleDeleteBudget = async (budgetId: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete budget policy '${name}'?`)) return;
    try {
      await api.delete(`/billing/budgets/${budgetId}`);
      setActionSuccessMsg(`Budget policy '${name}' deleted.`);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to delete budget', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to delete budget.');
    }
  };

  const handleEvaluateBudgets = async () => {
    setIsEvaluatingBudgets(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      const res = await api.post(`/billing/budgets/evaluate${activeWorkspace ? `?workspace_id=${activeWorkspace.id}` : ''}`);
      const data: BudgetEvaluationResult = res.data;
      if (data.triggered_alerts_count > 0) {
        setActionSuccessMsg(`Budget evaluation complete: ${data.triggered_alerts_count} new threshold alerts dispatched.`);
      } else {
        setActionSuccessMsg(`Budget evaluation complete: all ${data.evaluated_budgets} active budgets are within current thresholds.`);
      }
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 5000);
    } catch (err: any) {
      console.error('Failed to evaluate budgets', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to evaluate budgets.');
    } finally {
      setIsEvaluatingBudgets(false);
    }
  };

  const handleOpenPublishVersionModal = (plan: SubscriptionPlan) => {
    setSelectedPlanForVersion(plan);
    const curr = plan.active_pricing || (plan.pricing_versions && plan.pricing_versions[plan.pricing_versions.length - 1]);
    setPubMonthlyPrice(curr ? curr.monthly_base_price.toString() : '9999');
    setPubAnnualPrice(curr ? curr.annual_base_price.toString() : '99990');
    setPubIncludedRuns(curr ? curr.included_pipeline_runs.toString() : '10000');
    setPubBasicRate(curr ? curr.basic_run_rate.toString() : '0.50');
    setPubStandardRate(curr ? curr.standard_run_rate.toString() : '1.50');
    setPubAdvancedRate(curr ? curr.advanced_run_rate.toString() : '3.00');
    setPubComplexRate(curr ? curr.complex_run_rate.toString() : '5.00');
    setPubSparkRate(curr ? curr.spark_node_hour_rate.toString() : '45.0');
    setPubCurrency(curr ? curr.currency : 'INR');
    setPubJustification('Regular indexation and tier capacity revision');
    setIsPublishModalOpen(true);
  };

  const handlePublishPricingVersion = async () => {
    if (!selectedPlanForVersion || !pubJustification.trim()) {
      setActionErrorMsg('Administrative justification is strictly mandatory for pricing audit trails.');
      return;
    }
    setIsPublishingVersion(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      await api.post(`/billing/admin/plans/${selectedPlanForVersion.id}/pricing-versions`, {
        monthly_base_price: parseFloat(pubMonthlyPrice) || 0.0,
        annual_base_price: parseFloat(pubAnnualPrice) || 0.0,
        included_pipeline_runs: parseInt(pubIncludedRuns) || 0,
        basic_run_rate: parseFloat(pubBasicRate) || 0.50,
        standard_run_rate: parseFloat(pubStandardRate) || 1.50,
        advanced_run_rate: parseFloat(pubAdvancedRate) || 3.00,
        complex_run_rate: parseFloat(pubComplexRate) || 5.00,
        spark_node_hour_rate: parseFloat(pubSparkRate) || 45.0,
        currency: pubCurrency,
        justification: pubJustification.trim()
      });
      setActionSuccessMsg(`New pricing schedule published for plan '${selectedPlanForVersion.name}'. Historical invoices preserved.`);
      setIsPublishModalOpen(false);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 5000);
    } catch (err: any) {
      console.error('Failed to publish pricing version', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to publish new pricing version.');
    } finally {
      setIsPublishingVersion(false);
    }
  };

  const handleOpenCustomAgreementModal = () => {
    setCustomTenantId(overview?.tenant?.id || '');
    setCustomPlanName('Enterprise Dedicated Volume Agreement');
    setCustomMonthlyPrice('150000');
    setCustomAnnualPrice('1500000');
    setCustomIncludedRuns('750000');
    setCustomBasicRate('0.30');
    setCustomStandardRate('1.00');
    setCustomAdvancedRate('2.00');
    setCustomComplexRate('3.50');
    setCustomSparkRate('30.0');
    setCustomNotes('Negotiated high-scale enterprise volume contract with dedicated SLA');
    setCustomJustification('Contract approved by executive management');
    setIsCustomAgreementModalOpen(true);
  };

  const handleSaveCustomAgreement = async () => {
    if (!customTenantId.trim() || !customJustification.trim()) {
      setActionErrorMsg('Tenant ID and administrative justification are required.');
      return;
    }
    setIsSavingCustomAgreement(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      await api.post('/billing/admin/custom-agreement', {
        tenant_id: customTenantId.trim(),
        plan_name: customPlanName.trim(),
        monthly_base_price: parseFloat(customMonthlyPrice) || 0.0,
        annual_base_price: parseFloat(customAnnualPrice) || 0.0,
        included_pipeline_runs: parseInt(customIncludedRuns) || 0,
        basic_run_rate: parseFloat(customBasicRate) || 0.0,
        standard_run_rate: parseFloat(customStandardRate) || 0.0,
        advanced_run_rate: parseFloat(customAdvancedRate) || 0.0,
        complex_run_rate: parseFloat(customComplexRate) || 0.0,
        spark_node_hour_rate: parseFloat(customSparkRate) || 0.0,
        currency: 'INR',
        custom_agreement_notes: customNotes.trim(),
        justification: customJustification.trim()
      });
      setActionSuccessMsg('Bespoke enterprise agreement successfully provisioned.');
      setIsCustomAgreementModalOpen(false);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 5000);
    } catch (err: any) {
      console.error('Failed to provision custom agreement', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to provision custom agreement.');
    } finally {
      setIsSavingCustomAgreement(false);
    }
  };

  const handleOpenAdjustmentModal = (invoiceId?: string) => {
    setAdjInvoiceId(invoiceId || (invoices.length > 0 ? invoices[0].id : ''));
    setAdjAmount('2000');
    setAdjType('GoodwillSLA');
    setAdjDesc('Incident SLA credit adjustment per customer request');
    setAdjJustification('Approved per incident ticket SLA-9081');
    setIsAdjustmentModalOpen(true);
  };

  const handleApplyAdjustment = async () => {
    if (!adjInvoiceId || !adjAmount || !adjJustification.trim()) {
      setActionErrorMsg('Invoice ID, credit amount, and justification are required.');
      return;
    }
    setIsApplyingAdjustment(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);
    try {
      await api.post(`/billing/admin/invoices/${adjInvoiceId}/adjustments`, {
        adjustment_amount: parseFloat(adjAmount) || 0.0,
        adjustment_type: adjType,
        description: adjDesc.trim(),
        justification: adjJustification.trim()
      });
      setActionSuccessMsg(`Credit adjustment of ₹${parseFloat(adjAmount).toLocaleString()} applied to invoice.`);
      setIsAdjustmentModalOpen(false);
      await fetchData();
      setTimeout(() => setActionSuccessMsg(null), 5000);
    } catch (err: any) {
      console.error('Failed to apply invoice adjustment', err);
      setActionErrorMsg(err.response?.data?.detail || 'Failed to apply adjustment.');
    } finally {
      setIsApplyingAdjustment(false);
    }
  };

  // Filtered & Paginated usage entries
  const filteredUsage = (() => {
    const sourceList: any[] = usageLedger.length > 0 ? usageLedger : recentRuns.map((r: any) => {
      const acts = r.activity_runs ? r.activity_runs.length : 1;
      let classification = 'Basic';
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
        duration_seconds: r.duration_seconds || 10,
        rows_processed: (r.total_rows_read || 0) + (r.total_rows_written || 0),
        bytes_processed: r.total_bytes_processed || 0,
        is_billable: r.status !== 'Cancelled',
        calculated_charge: r.status !== 'Cancelled' ? rate : 0.0,
        non_billable_reason: r.status === 'Cancelled' ? 'UserCancelled' : undefined
      };
    });

    return sourceList.filter((item) => {
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = item.pipeline_name?.toLowerCase().includes(q);
        const matchesRunId = item.pipeline_run_id?.toLowerCase().includes(q);
        if (!matchesName && !matchesRunId) return false;
      }
      // Engine
      if (filterEngine !== 'ALL' && item.execution_engine !== filterEngine) return false;
      // Classification
      if (filterClassification !== 'ALL' && item.classification !== filterClassification) return false;
      // Billability
      if (filterBillable === 'BILLABLE' && !item.is_billable) return false;
      if (filterBillable === 'NON_BILLABLE' && item.is_billable) return false;
      // Date Range
      if (filterDateRange !== 'all' && item.started_at) {
        const itemDate = new Date(item.started_at);
        const now = new Date();
        if (filterDateRange === 'today') {
          if (itemDate.toDateString() !== now.toDateString()) return false;
        } else if (filterDateRange === '7d') {
          if (now.getTime() - itemDate.getTime() > 7 * 86400000) return false;
        } else if (filterDateRange === '30d') {
          if (now.getTime() - itemDate.getTime() > 30 * 86400000) return false;
        }
      }
      return true;
    });
  })();

  const totalPages = Math.max(1, Math.ceil(filteredUsage.length / pageSize));
  const paginatedUsage = filteredUsage.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Estimator Calculations
  const calculateEstimator = (): CostEstimateResult => {
    let classification = 'Basic';
    let ratePerRun = 0.50;

    if (estActivities <= 5) {
      classification = 'Basic';
      ratePerRun = 0.50;
    } else if (estActivities <= 15) {
      classification = 'Standard';
      ratePerRun = 1.50;
    } else if (estActivities <= 30) {
      classification = 'Advanced';
      ratePerRun = 3.00;
    } else {
      classification = 'Complex';
      ratePerRun = 5.00;
    }

    const isAnnual = estPeriod === 'Annual';

    let recPlan = 'starter';
    let recPlanName = 'Starter Plan';
    if (estRuns <= 10000 && sparkEnginePct === 0) {
      recPlan = 'starter';
      recPlanName = 'Starter Plan';
    } else if (estRuns <= 80000) {
      recPlan = 'professional';
      recPlanName = 'Professional Plan';
    } else {
      recPlan = 'enterprise';
      recPlanName = 'Enterprise Plan';
    }

    const sparkHours = runtimeHours * (sparkEnginePct / 100);
    const sparkCost = deploymentModel === 'SaaS' ? Math.round(sparkHours * 45) : 0;

    const tierSpecs = [
      {
        plan_code: 'starter',
        plan_name: 'Starter Plan',
        tier_level: 1,
        monthly_base_price: isAnnual ? 8332.50 : 9999,
        included_runs: 10000,
        features_summary: ['Basic Copy Engine', 'Database & Storage Connectors', 'Basic Data Quality', 'Standard Support']
      },
      {
        plan_code: 'professional',
        plan_name: 'Professional Plan',
        tier_level: 2,
        monthly_base_price: isAnnual ? 24999.17 : 29999,
        included_runs: 50000,
        features_summary: ['Advanced Copy Engine', 'Managed Spark Engine', 'SQL Pushdown Engine', 'Data Reconciliation', 'Git Integration', 'Priority Support']
      },
      {
        plan_code: 'enterprise',
        plan_name: 'Enterprise Plan',
        tier_level: 3,
        monthly_base_price: isAnnual ? 83332.50 : 99999,
        included_runs: 250000,
        features_summary: ['Self-Hosted Runtimes', 'Advanced Security & RBAC', 'Audit Logs & Governance', '24/7 Enterprise SLA', 'Custom Connectors']
      }
    ];

    const planComparison: PlanComparisonItem[] = tierSpecs.map(spec => {
      const overageRuns = Math.max(0, estRuns - spec.included_runs);
      const overageCost = Math.round(overageRuns * ratePerRun);
      const subtotal = spec.monthly_base_price + overageCost + sparkCost;
      const gst = Math.round(subtotal * 0.18);
      const total = subtotal + gst;
      return {
        ...spec,
        overage_runs: overageRuns,
        overage_cost: overageCost,
        spark_compute_cost: sparkCost,
        software_subtotal: subtotal,
        estimated_gst_tax: gst,
        software_total: total,
        is_recommended: spec.plan_code === recPlan
      };
    });

    const recItem = planComparison.find(p => p.plan_code === recPlan)!;

    // Infrastructure estimates (Customer Cloud in BYOC)
    const storageEst = Math.round(dataVolumeGB * 1.65);
    const computeNodesEst = Math.round(Math.min(8000, Math.max(1200, (estRuns / 10000) * 1500)));
    const infraTotal = storageEst + computeNodesEst;

    // ADF Comparison
    const adfActivityRuns = estRuns * estActivities;
    const adfOrchestration = (adfActivityRuns / 1000) * 83;
    const adfDataflow = sparkHours * 176;
    const adfPipelinesFee = estPipelines * 125;
    const adfTotal = Math.max(recItem.software_total * 1.45, Math.round(adfOrchestration + adfDataflow + adfPipelinesFee));
    const savingsPercent = Math.max(10, Math.round(((adfTotal - recItem.software_total) / adfTotal) * 100));

    return {
      recommended_plan: recPlan,
      recommended_plan_name: recPlanName,
      billing_period: estPeriod,
      deployment_model: deploymentModel,
      expected_monthly_runs: estRuns,
      activity_classification: classification,
      rate_per_overage_run: ratePerRun,
      included_runs: recItem.included_runs,
      overage_runs: recItem.overage_runs,
      base_subscription_cost: recItem.monthly_base_price,
      overage_cost: recItem.overage_cost,
      spark_compute_cost: sparkCost,
      estimated_software_subtotal: recItem.software_subtotal,
      estimated_tax_gst: recItem.estimated_gst_tax,
      estimated_software_total: recItem.software_total,
      estimated_cloud_infrastructure_cost: infraTotal,
      cloud_markup_percent: 0.0,
      estimated_adf_equivalent_cost: adfTotal,
      estimated_savings_percent: savingsPercent,
      plan_comparison: planComparison,
      assumptions_and_limitations: [
        `Pipeline complexity rated as '${classification}' based on ${estActivities} activities/pipeline (₹${ratePerRun.toFixed(2)}/run overage rate).`,
        `Commitment: ${estPeriod} subscription (${isAnnual ? '17% annual prepayment discount included' : 'standard monthly'}).`,
        'Taxes: Standard 18.00% Indian GST calculated on platform software subtotal.',
        'BYOC Mode: DataForge charges 0% vendor markup on customer cloud compute or storage. Cloud infrastructure charges are estimates paid directly to your cloud provider.',
        'SQL Pushdown Engine: Zero egress fees for ELT transformations executed natively inside your data warehouse.'
      ]
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
          { id: 'budgets', label: 'Budgets & Threshold Alerts', icon: Bell },
          { id: 'admin', label: 'Admin Pricing & Audit', icon: ShieldCheck },
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
        </div>
      )}

      {/* TAB 2: PLANS & TIERS */}
      {activeTab === 'plans' && (
        <div className="space-y-6">
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
        </div>
      )}

      {/* TAB 3: PIPELINE USAGE LEDGER */}
      {activeTab === 'usage' && (
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-white">Immutable Pipeline Usage Ledger</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Every pipeline execution generates an immutable usage record with complexity classification and billable status. Click any row for details.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
              >
                <Download className="h-3.5 w-3.5" />
                Export CSV
              </button>
            </div>
          </div>

          {/* Search & Advanced Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5 p-3.5 bg-slate-950/70 rounded-xl border border-slate-800 text-xs">
            <div className="relative">
              <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search pipeline or run ID..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg pl-8 pr-2.5 py-1.5 text-xs outline-none focus:border-brand-500"
              />
            </div>

            <select
              value={filterEngine}
              onChange={(e) => { setFilterEngine(e.target.value); setCurrentPage(1); }}
              className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-brand-500"
            >
              <option value="ALL">All Engines</option>
              <option value="CopyEngine">Parallel Copy Engine</option>
              <option value="SparkEngine">Distributed Spark Engine</option>
              <option value="SqlPushdownEngine">In-DB SQL Pushdown</option>
              <option value="Hybrid">Hybrid DAGs</option>
            </select>

            <select
              value={filterClassification}
              onChange={(e) => { setFilterClassification(e.target.value); setCurrentPage(1); }}
              className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-brand-500"
            >
              <option value="ALL">All Complexity Tiers</option>
              <option value="Basic">Basic (1–5 activities)</option>
              <option value="Standard">Standard (6–15 activities)</option>
              <option value="Advanced">Advanced (16–30 activities)</option>
              <option value="Complex">Complex (31+ activities)</option>
            </select>

            <select
              value={filterBillable}
              onChange={(e) => { setFilterBillable(e.target.value); setCurrentPage(1); }}
              className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-brand-500"
            >
              <option value="ALL">All Billability</option>
              <option value="BILLABLE">Billable Only</option>
              <option value="NON_BILLABLE">Non-Billable (System/Cancelled)</option>
            </select>

            <select
              value={filterDateRange}
              onChange={(e) => { setFilterDateRange(e.target.value as any); setCurrentPage(1); }}
              className="bg-slate-900 border border-slate-700 text-white rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-brand-500"
            >
              <option value="all">All Dates</option>
              <option value="today">Today</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Run ID</th>
                  <th className="py-2.5 px-3">Pipeline</th>
                  <th className="py-2.5 px-3">Engine</th>
                  <th className="py-2.5 px-3 text-center">Activities</th>
                  <th className="py-2.5 px-3">Tier</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Billable</th>
                  <th className="py-2.5 px-3 text-right">Charge</th>
                  <th className="py-2.5 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {paginatedUsage.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-8 text-center text-slate-500 font-sans">
                      No matching pipeline usage entries found.
                    </td>
                  </tr>
                ) : (
                  paginatedUsage.map((entry: any) => (
                    <tr 
                      key={entry.id} 
                      onClick={() => setSelectedRunForDrawer(entry)}
                      className="hover:bg-slate-800/40 transition cursor-pointer group"
                    >
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {entry.started_at ? new Date(entry.started_at).toLocaleString() : 'Recent'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 truncate max-w-[100px]" title={entry.pipeline_run_id}>
                        {entry.pipeline_run_id.substring(0, 8)}...
                      </td>
                      <td className="py-2.5 px-3 text-white font-sans font-medium truncate max-w-[150px] group-hover:text-brand-300 transition">
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
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelectedRunForDrawer(entry); }}
                          className="px-2 py-1 rounded text-[10px] text-brand-400 hover:text-brand-300 hover:bg-slate-800 transition"
                        >
                          View Breakdown
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Toolbar */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-800 text-xs">
            <span className="text-slate-400">
              Showing {Math.min(filteredUsage.length, (currentPage - 1) * pageSize + 1)} to {Math.min(filteredUsage.length, currentPage * pageSize)} of {filteredUsage.length} metered runs
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 transition"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-mono text-slate-300 px-2">Page {currentPage} of {totalPages}</span>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 transition"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: CONSUMPTION BREAKDOWN & CHARTS */}
      {activeTab === 'consumption' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock className="h-4 w-4 text-brand-400" />
                ADF-Parity Visual Consumption Reports & Engine Splits
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Aggregated consumption metrics, Spark node-hours, in-DB SQL Pushdown, and daily trend curves.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExportJSON}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
              >
                <Download className="h-3.5 w-3.5" />
                Export JSON
              </button>
              <button
                onClick={handleRecalculateRating}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 shadow-sm transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Recalculate Rollups
              </button>
            </div>
          </div>

          {/* Engine Distribution Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">Parallel Copy Engine</span>
                <span className="p-1.5 rounded bg-blue-500/10 text-blue-400"><Server className="h-4 w-4" /></span>
              </div>
              <div className="mt-3">
                <span className="text-2xl font-bold text-white font-mono">
                  {consumptionSummary?.engine_breakdown.CopyEngine ?? 0}
                </span>
                <span className="text-xs text-slate-400 block mt-0.5">Streaming pipeline runs</span>
              </div>
              <div className="mt-3 text-[11px] text-emerald-400 font-mono">
                Memory: &le;64 MB/partition
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">Managed Spark Engine</span>
                <span className="p-1.5 rounded bg-purple-500/10 text-purple-400"><Zap className="h-4 w-4" /></span>
              </div>
              <div className="mt-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-white font-mono">
                    {consumptionSummary?.engine_breakdown.SparkEngine ?? 0}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    ({consumptionSummary?.spark_node_hours.toFixed(2) ?? '0.00'} node-hrs)
                  </span>
                </div>
                <span className="text-xs text-slate-400 block mt-0.5">Heavy ETL & PySpark jobs</span>
              </div>
              <div className="mt-3 text-[11px] text-purple-400 font-mono">
                Rate: ₹45.00 / node-hour
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">In-DB SQL Pushdown</span>
                <span className="p-1.5 rounded bg-emerald-500/10 text-emerald-400"><ShieldCheck className="h-4 w-4" /></span>
              </div>
              <div className="mt-3">
                <span className="text-2xl font-bold text-white font-mono">
                  {consumptionSummary?.engine_breakdown.SqlPushdownEngine ?? 0}
                </span>
                <span className="text-xs text-slate-400 block mt-0.5">Zero-egress warehouse transforms</span>
              </div>
              <div className="mt-3 text-[11px] text-emerald-400 font-mono">
                Network Egress: ₹0.00 (Free)
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">Hybrid DAGs</span>
                <span className="p-1.5 rounded bg-amber-500/10 text-amber-400"><Layers className="h-4 w-4" /></span>
              </div>
              <div className="mt-3">
                <span className="text-2xl font-bold text-white font-mono">
                  {consumptionSummary?.engine_breakdown.Hybrid ?? 0}
                </span>
                <span className="text-xs text-slate-400 block mt-0.5">Multi-engine DAG executions</span>
              </div>
              <div className="mt-3 text-[11px] text-slate-400 font-mono">
                Automatic Engine Affinity
              </div>
            </div>
          </div>

          {/* Recharts Graphical Consumption Visualizer */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-brand-400" />
                  Daily Execution Volume & Complexity Progression
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">
                  Visual activity complexity and engine distribution over time.
                </p>
              </div>

              <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 self-start sm:self-auto text-xs">
                <button
                  onClick={() => setConsumptionChartMode('tiers')}
                  className={`px-2.5 py-1 rounded transition ${
                    consumptionChartMode === 'tiers' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  By Complexity
                </button>
                <button
                  onClick={() => setConsumptionChartMode('engines')}
                  className={`px-2.5 py-1 rounded transition ${
                    consumptionChartMode === 'engines' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  By Engine
                </button>
              </div>
            </div>

            {(!consumptionSummary?.daily_consumption || consumptionSummary.daily_consumption.length === 0) ? (
              <div className="py-12 text-center text-slate-500 text-xs font-sans">
                No daily execution time-series recorded in the current period yet.
              </div>
            ) : (
              <div className="h-64 w-full pt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={consumptionSummary.daily_consumption}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px', color: '#fff' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                    {consumptionChartMode === 'tiers' ? (
                      <>
                        <Bar dataKey="basic_runs" name="Basic (₹0.50)" stackId="a" fill="#3b82f6" />
                        <Bar dataKey="standard_runs" name="Standard (₹1.50)" stackId="a" fill="#10b981" />
                        <Bar dataKey="advanced_runs" name="Advanced (₹3.00)" stackId="a" fill="#f59e0b" />
                        <Bar dataKey="complex_runs" name="Complex (₹5.00)" stackId="a" fill="#ec4899" />
                      </>
                    ) : (
                      <>
                        <Bar dataKey="copy_runs" name="Copy Engine" stackId="b" fill="#3b82f6" />
                        <Bar dataKey="spark_runs" name="Spark Engine" stackId="b" fill="#a855f7" />
                        <Bar dataKey="sql_runs" name="SQL Pushdown" stackId="b" fill="#10b981" />
                      </>
                    )}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
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
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <FileText className="h-5 w-5 text-brand-400" />
                  Tax Invoices & Billing Statements
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Compliant GST (18.0%) tax statements, itemized line items, and offline bank transfer payment receipts.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-slate-400 hidden md:inline">
                  Tax Policy: Standard 18% GST (CGST 9% + SGST 9%)
                </span>
                <button
                  onClick={handleGenerateInvoice}
                  disabled={isGeneratingInvoice}
                  className="px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 transition shadow-lg shadow-brand-500/20 flex items-center gap-2 disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isGeneratingInvoice ? 'animate-spin' : ''}`} />
                  {isGeneratingInvoice ? 'Generating...' : '+ Generate Statement'}
                </button>
              </div>
            </div>

            {invoices.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-slate-800 rounded-xl space-y-3">
                <FileText className="h-10 w-10 text-slate-600 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-300">No Invoices Issued Yet</h4>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Monthly billing statements are generated at the end of each billing cycle or can be generated on-demand for the current cycle.
                </p>
                <button
                  onClick={handleGenerateInvoice}
                  disabled={isGeneratingInvoice}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition"
                >
                  Generate Current Period Statement
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                      <th className="py-3 px-3">Invoice Number</th>
                      <th className="py-3 px-3">Period</th>
                      <th className="py-3 px-3">Issue Date</th>
                      <th className="py-3 px-3">Due Date</th>
                      <th className="py-3 px-3">Subscription</th>
                      <th className="py-3 px-3">Usage & Compute</th>
                      <th className="py-3 px-3">GST (18%)</th>
                      <th className="py-3 px-3">Total Payable</th>
                      <th className="py-3 px-3">Status</th>
                      <th className="py-3 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {invoices.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 px-3 text-white font-medium">
                          <button
                            onClick={() => handleOpenInvoiceDetail(inv)}
                            className="text-brand-400 hover:text-brand-300 underline font-mono flex items-center gap-1"
                          >
                            {inv.invoice_number}
                          </button>
                        </td>
                        <td className="py-3 px-3 text-slate-300 font-sans">{inv.period_key}</td>
                        <td className="py-3 px-3 text-slate-400 font-sans">{new Date(inv.issue_date).toLocaleDateString()}</td>
                        <td className="py-3 px-3 text-slate-400 font-sans">{new Date(inv.due_date).toLocaleDateString()}</td>
                        <td className="py-3 px-3 text-slate-300">₹{Number(inv.subscription_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        <td className="py-3 px-3 text-slate-300">₹{(Number(inv.overage_amount) + Number(inv.compute_amount)).toFixed(2)}</td>
                        <td className="py-3 px-3 text-slate-300">₹{Number(inv.tax_amount).toFixed(2)}</td>
                        <td className="py-3 px-3 text-white font-bold">₹{Number(inv.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                        <td className="py-3 px-3 font-sans">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                            inv.status === 'Paid'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : inv.status === 'Issued'
                              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                              : 'bg-slate-800 text-slate-400 border-slate-700'
                          }`}>
                            {inv.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-sans">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleDownloadInvoicePDF(inv.id, inv.invoice_number)}
                              title="Download ISO 32000-1 PDF"
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 flex items-center gap-1 text-[11px] transition"
                            >
                              <Download className="h-3 w-3" /> PDF
                            </button>
                            {inv.status !== 'Paid' && (
                              <button
                                onClick={() => handleOpenPaymentModal(inv)}
                                title="Record Wire / Bank Transfer"
                                className="px-2 py-1 rounded bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 border border-brand-500/30 text-[11px] font-medium transition"
                              >
                                Record Pay
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 7: COST ESTIMATOR */}
      {activeTab === 'estimator' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Sizing Workload Inputs */}
            <div className="lg:col-span-7 p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-5">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-brand-400" />
                  Workload Modeling & Sizing Calculator
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Adjust expected orchestration runs, pipeline complexity, execution engines, and cloud deployment model.
                </p>
              </div>

              {/* Monthly Pipeline Runs */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-200">Expected Monthly Pipeline Runs</label>
                  <span className="text-sm font-bold text-brand-400 font-mono">{estRuns.toLocaleString()} runs/mo</span>
                </div>
                <input
                  type="range"
                  min={1000}
                  max={300000}
                  step={1000}
                  value={estRuns}
                  onChange={(e) => setEstRuns(Number(e.target.value))}
                  className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>1k</span>
                  <span>10k (Starter)</span>
                  <span>50k (Pro)</span>
                  <span>250k (Enterprise)</span>
                  <span>300k+</span>
                </div>
              </div>

              {/* Grid 2-col: Active Pipelines & Activities per Pipeline */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200">Active Pipelines Count</label>
                    <span className="text-xs font-bold text-white font-mono">{estPipelines} pipelines</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={100}
                    step={1}
                    value={estPipelines}
                    onChange={(e) => setEstPipelines(Number(e.target.value))}
                    className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>1</span>
                    <span>50</span>
                    <span>100</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200">Average Activities / DAG</label>
                    <span className="text-xs font-bold text-white font-mono">
                      {estActivities} acts ({estResult.activity_classification})
                    </span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={50}
                    step={1}
                    value={estActivities}
                    onChange={(e) => setEstActivities(Number(e.target.value))}
                    className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>Basic (≤5)</span>
                    <span>Std (6-15)</span>
                    <span>Adv (16-30)</span>
                    <span>Cmplx (31+)</span>
                  </div>
                </div>
              </div>

              {/* Execution Engine Distribution */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200">Engine Workload Share:</span>
                  <span className="text-[10px] text-slate-400 font-mono">Copy: {copyEnginePct}% | Spark: {sparkEnginePct}% | Pushdown: {sqlPushdownPct}%</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Copy Engine %</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={copyEnginePct}
                      onChange={(e) => setCopyEnginePct(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Spark Engine %</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={sparkEnginePct}
                      onChange={(e) => setSparkEnginePct(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">SQL Pushdown %</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={sqlPushdownPct}
                      onChange={(e) => setSqlPushdownPct(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-brand-500"
                    />
                  </div>
                </div>
              </div>

              {/* Data Volume & Runtime Hours */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200">Monthly Data Volume</label>
                    <span className="text-xs font-bold text-white font-mono">{dataVolumeGB} GB/mo</span>
                  </div>
                  <input
                    type="range"
                    min={10}
                    max={5000}
                    step={50}
                    value={dataVolumeGB}
                    onChange={(e) => setDataVolumeGB(Number(e.target.value))}
                    className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>10 GB</span>
                    <span>1 TB</span>
                    <span>5 TB</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-200">Execution Compute Hours</label>
                    <span className="text-xs font-bold text-white font-mono">{runtimeHours} hrs/mo</span>
                  </div>
                  <input
                    type="range"
                    min={10}
                    max={500}
                    step={10}
                    value={runtimeHours}
                    onChange={(e) => setRuntimeHours(Number(e.target.value))}
                    className="w-full accent-brand-500 bg-slate-800 h-2 rounded-lg cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>10 hrs</span>
                    <span>200 hrs</span>
                    <span>500 hrs</span>
                  </div>
                </div>
              </div>

              {/* Deployment Model & Billing Commitment */}
              <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-300 font-medium">Deployment:</span>
                  <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      onClick={() => setDeploymentModel('BYOC')}
                      className={`px-2.5 py-1 rounded text-xs transition ${
                        deploymentModel === 'BYOC' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400'
                      }`}
                    >
                      BYOC (0% Markup)
                    </button>
                    <button
                      onClick={() => setDeploymentModel('SaaS')}
                      className={`px-2.5 py-1 rounded text-xs transition ${
                        deploymentModel === 'SaaS' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400'
                      }`}
                    >
                      SaaS Managed
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-300 font-medium">Term:</span>
                  <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      onClick={() => setEstPeriod('Monthly')}
                      className={`px-2.5 py-1 rounded text-xs transition ${
                        estPeriod === 'Monthly' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400'
                      }`}
                    >
                      Monthly
                    </button>
                    <button
                      onClick={() => setEstPeriod('Annual')}
                      className={`px-2.5 py-1 rounded text-xs transition ${
                        estPeriod === 'Annual' ? 'bg-brand-600 text-white font-semibold' : 'text-slate-400'
                      }`}
                    >
                      Annual (-17%)
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Workload Recommendation & Sizing */}
            <div className="lg:col-span-5 p-6 rounded-2xl bg-gradient-to-b from-slate-900 to-brand-950/30 border border-slate-800 flex flex-col justify-between space-y-6">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-brand-400 uppercase tracking-wider block">
                    Recommended Plan Tier
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20 uppercase">
                    {estResult.activity_classification} Tier
                  </span>
                </div>

                <h3 className="text-xl font-bold text-white capitalize mt-1.5 flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-amber-400" />
                  {estResult.recommended_plan_name}
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Provides {estResult.included_runs.toLocaleString()} included executions/month with ₹{estResult.rate_per_overage_run.toFixed(2)} rate per additional run.
                </p>

                <div className="mt-5 space-y-2.5 text-xs">
                  <div className="flex justify-between py-1.5 border-b border-slate-800">
                    <span className="text-slate-400">Base Subscription ({estPeriod})</span>
                    <span className="text-white font-mono font-semibold">₹{Math.round(estResult.base_subscription_cost).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-800">
                    <span className="text-slate-400">Included Executions Allowance</span>
                    <span className="text-emerald-400 font-mono">{estResult.included_runs.toLocaleString()} runs</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-800">
                    <span className="text-slate-400">Estimated Overage ({estResult.overage_runs.toLocaleString()} runs)</span>
                    <span className="text-white font-mono font-semibold">₹{Math.round(estResult.overage_cost).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-800">
                    <span className="text-slate-400">Managed Spark Compute ({deploymentModel})</span>
                    <span className="text-white font-mono font-semibold">₹{Math.round(estResult.spark_compute_cost).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-800">
                    <span className="text-slate-400">Indian GST (18.0%)</span>
                    <span className="text-slate-300 font-mono">₹{Math.round(estResult.estimated_tax_gst).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between py-2 pt-3 font-bold text-white text-base">
                    <span>Total Estimated DataForge Cost</span>
                    <span className="text-brand-400 font-mono">₹{Math.round(estResult.estimated_software_total).toLocaleString()}<span className="text-xs text-slate-400">/mo</span></span>
                  </div>
                </div>

                {/* Cloud & ADF Comparison */}
                <div className="mt-4 p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Estimated Cloud Infra ({deploymentModel}):</span>
                    <span className="text-slate-300 font-mono">~₹{Math.round(estResult.estimated_cloud_infrastructure_cost).toLocaleString()}/mo</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Azure Data Factory Equivalent:</span>
                    <span className="text-slate-300 font-mono line-through">₹{Math.round(estResult.estimated_adf_equivalent_cost).toLocaleString()}/mo</span>
                  </div>
                  <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800">
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Estimated Savings vs ADF:
                    </span>
                    <span className="text-emerald-400 font-bold font-mono text-sm">~{estResult.estimated_savings_percent}% lower</span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => {
                  const targetPlan = plans.find(p => p.plan_code === estResult.recommended_plan);
                  if (targetPlan) {
                    handlePlanSwitch(targetPlan.id, estPeriod);
                  }
                }}
                disabled={isUpdatingSub}
                className="w-full py-3 rounded-xl text-xs font-bold text-white bg-brand-600 hover:bg-brand-500 shadow-lg shadow-brand-600/30 transition flex items-center justify-center gap-2"
              >
                <Sparkles className="h-4 w-4" />
                Subscribe to {estResult.recommended_plan_name.toUpperCase()}
              </button>
            </div>
          </div>

          {/* Side-by-Side 3-Tier Plan Comparison Matrix */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div>
              <h3 className="text-sm font-bold text-white">Side-by-Side Commercial Plan Comparison</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Compare Starter, Professional, and Enterprise options for your simulated workload of {estRuns.toLocaleString()} runs.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                    <th className="py-3 px-3">Plan Tier</th>
                    <th className="py-3 px-3">Base Subscription</th>
                    <th className="py-3 px-3">Included Allowance</th>
                    <th className="py-3 px-3">Simulated Overages</th>
                    <th className="py-3 px-3">Overage Surcharge</th>
                    <th className="py-3 px-3">Total Monthly (incl. GST)</th>
                    <th className="py-3 px-3">Effective Rate / Run</th>
                    <th className="py-3 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {estResult.plan_comparison.map((tier) => {
                    const effectiveRate = tier.software_total / estRuns;
                    return (
                      <tr
                        key={tier.plan_code}
                        className={`transition ${tier.is_recommended ? 'bg-brand-500/5 hover:bg-brand-500/10' : 'hover:bg-slate-800/30'}`}
                      >
                        <td className="py-3 px-3 font-sans">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white text-sm">{tier.plan_name}</span>
                            {tier.is_recommended && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                RECOMMENDED
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-400 block mt-0.5 font-sans">
                            {tier.features_summary.slice(0, 2).join(' • ')}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-slate-300">₹{Math.round(tier.monthly_base_price).toLocaleString()}/mo</td>
                        <td className="py-3 px-3 text-emerald-400">{tier.included_runs.toLocaleString()} runs</td>
                        <td className="py-3 px-3 text-slate-300">{tier.overage_runs.toLocaleString()} runs</td>
                        <td className="py-3 px-3 text-slate-300">₹{tier.overage_cost.toLocaleString()}</td>
                        <td className="py-3 px-3 text-brand-400 font-bold text-sm">₹{tier.software_total.toLocaleString()}</td>
                        <td className="py-3 px-3 text-slate-300">₹{effectiveRate.toFixed(2)} / run</td>
                        <td className="py-3 px-3 text-right font-sans">
                          <button
                            onClick={() => {
                              const target = plans.find(p => p.plan_code === tier.plan_code);
                              if (target) handlePlanSwitch(target.id, estPeriod);
                            }}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                              tier.is_recommended
                                ? 'bg-brand-600 hover:bg-brand-500 text-white shadow-md shadow-brand-600/30'
                                : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700'
                            }`}
                          >
                            Select Plan
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Stated Assumptions & Limitations */}
          <div className="p-5 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2.5">
            <h4 className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
              <Info className="h-4 w-4 text-slate-400" />
              Transparent Pricing Model Assumptions & Limitations
            </h4>
            <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
              {estResult.assumptions_and_limitations.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* TAB 8: BUDGETS & THRESHOLD ALERTS */}
      {activeTab === 'budgets' && (
        <div className="space-y-6">
          {/* Header Action & Summary KPIs */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Bell className="h-5 w-5 text-brand-400" />
                Budget Controls & Automated Threshold Alerts
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Configure spending and execution caps, automated alerts (50%, 75%, 90%, 100%), and optional hard-stop execution prevention.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleEvaluateBudgets}
                disabled={isEvaluatingBudgets || budgets.length === 0}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isEvaluatingBudgets ? 'animate-spin' : ''}`} />
                {isEvaluatingBudgets ? 'Evaluating...' : 'Evaluate All Budgets'}
              </button>
              <button
                onClick={handleOpenCreateBudgetModal}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 shadow-lg shadow-brand-500/20 transition flex items-center gap-1.5"
              >
                <Plus className="h-4 w-4" />
                Create Budget Policy
              </button>
            </div>
          </div>

          {/* Hard Limit Warning Banner (If breached) */}
          {budgets.some(b => b.is_hard_limit_breached) && (
            <div className="p-4 rounded-xl bg-red-950/70 border border-red-700/80 flex items-start gap-3 text-red-200 text-xs animate-in fade-in">
              <ShieldAlert className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-red-100">Execution Prevention Safeguard Triggered:</span>{' '}
                One or more workspace budgets have reached 100% of their configured limits with hard stop enforcement active. 
                New pipeline executions are temporarily blocked until limits are adjusted or next billing period commences.
              </div>
            </div>
          )}

          {/* KPI Stat Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Active Budget Policies</span>
                <Target className="h-4 w-4 text-brand-400" />
              </div>
              <div className="text-xl font-bold text-white font-mono">{budgets.length}</div>
              <div className="text-[11px] text-slate-400">
                {budgets.some(b => b.enforce_hard_limit) ? (
                  <span className="text-rose-400 font-medium">Hard Stop Enabled</span>
                ) : (
                  <span className="text-emerald-400 font-medium">Warn-Only Telemetry</span>
                )}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Monthly Spending Cap</span>
                <DollarSign className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="text-xl font-bold text-white font-mono">
                ₹{budgets.reduce((acc, b) => acc + (b.monthly_limit_amount || 0), 0).toLocaleString()}
              </div>
              <div className="text-[11px] text-slate-400">
                Current Spend: <span className="font-mono text-white">₹{Math.round(budgets.length > 0 ? budgets.reduce((acc, b) => Math.max(acc, b.current_spend || 0), 0) : (overview?.estimated_total_software_charges || 0)).toLocaleString()}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Monthly Pipeline Run Cap</span>
                <Layers className="h-4 w-4 text-blue-400" />
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {budgets.reduce((acc, b) => acc + (b.monthly_run_limit || 0), 0) > 0 
                  ? budgets.reduce((acc, b) => acc + (b.monthly_run_limit || 0), 0).toLocaleString() 
                  : 'Uncapped'}
              </div>
              <div className="text-[11px] text-slate-400">
                Current Runs: <span className="font-mono text-white">{(budgets.length > 0 ? budgets.reduce((acc, b) => Math.max(acc, b.current_runs || 0), 0) : (overview?.consumed_runs || 0)).toLocaleString()}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Alerts Triggered (This Month)</span>
                <Bell className="h-4 w-4 text-amber-400" />
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {budgets.reduce((acc, b) => acc + (b.recent_alerts ? b.recent_alerts.length : 0), 0)}
              </div>
              <div className="text-[11px] text-slate-400">
                Threshold triggers (50%, 75%, 90%, 100%)
              </div>
            </div>
          </div>

          {/* Budget Policy List */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-200">Configured Budget Guardrails</h3>
            {budgets.length === 0 ? (
              <div className="p-10 rounded-2xl bg-slate-900 border border-slate-800 text-center space-y-3">
                <Target className="h-10 w-10 text-slate-600 mx-auto" />
                <h4 className="text-sm font-bold text-white">No Budget Policies Configured</h4>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Set up monthly spending or pipeline run limits to receive automated notifications when 50%, 75%, 90%, and 100% of your budget is reached.
                </p>
                <button
                  onClick={handleOpenCreateBudgetModal}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 transition shadow-lg shadow-brand-500/20"
                >
                  Configure Initial Budget
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {budgets.map((b) => {
                  const spendPct = Math.min(100, Math.round(b.spend_utilization_pct || 0));
                  const runPct = Math.min(100, Math.round(b.run_utilization_pct || 0));
                  const isHigh = spendPct >= 90 || runPct >= 90;
                  const isMid = (spendPct >= 75 || runPct >= 75) && !isHigh;

                  return (
                    <div
                      key={b.id}
                      className={`p-6 rounded-2xl bg-slate-900 border transition-all ${
                        b.is_hard_limit_breached
                          ? 'border-red-600 shadow-lg shadow-red-900/20'
                          : isHigh
                          ? 'border-amber-600/60'
                          : 'border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      {/* Card Header */}
                      <div className="flex items-start justify-between gap-3 mb-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-sm font-bold text-white">{b.name}</h4>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              b.enforce_hard_limit
                                ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                                : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                            }`}>
                              {b.enforce_hard_limit ? 'Hard Stop Protection' : 'Warn-Only'}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">
                            Scope: {b.workspace_id ? 'Workspace Specific' : 'Global Tenant-Wide'} • Period: {b.period_type}
                          </p>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleOpenEditBudgetModal(b)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                            title="Edit Budget"
                          >
                            <Edit3 className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteBudget(b.id, b.name)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition"
                            title="Delete Budget"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>

                      {/* Spend Utilization Gauge */}
                      <div className="space-y-2 mb-4">
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Monthly Spend Utilization</span>
                          <span className="font-mono text-white font-semibold">
                            ₹{b.current_spend.toLocaleString()} / ₹{b.monthly_limit_amount.toLocaleString()}{' '}
                            <span className={isHigh ? 'text-rose-400' : isMid ? 'text-amber-400' : 'text-emerald-400'}>
                              ({b.spend_utilization_pct.toFixed(1)}%)
                            </span>
                          </span>
                        </div>
                        <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              spendPct >= 90
                                ? 'bg-gradient-to-r from-red-600 to-rose-400'
                                : spendPct >= 75
                                ? 'bg-gradient-to-r from-amber-600 to-yellow-400'
                                : 'bg-gradient-to-r from-emerald-600 to-emerald-400'
                            }`}
                            style={{ width: `${spendPct}%` }}
                          />
                        </div>
                      </div>

                      {/* Run Count Utilization Gauge */}
                      {b.monthly_run_limit > 0 && (
                        <div className="space-y-2 mb-4">
                          <div className="flex justify-between text-xs">
                            <span className="text-slate-400">Pipeline Run Limit</span>
                            <span className="font-mono text-white font-semibold">
                              {b.current_runs.toLocaleString()} / {b.monthly_run_limit.toLocaleString()} runs{' '}
                              <span className={runPct >= 90 ? 'text-rose-400' : runPct >= 75 ? 'text-amber-400' : 'text-blue-400'}>
                                ({b.run_utilization_pct.toFixed(1)}%)
                              </span>
                            </span>
                          </div>
                          <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-400 transition-all duration-500"
                              style={{ width: `${runPct}%` }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Threshold Pills */}
                      <div className="pt-3 border-t border-slate-800/80 mb-4">
                        <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                          Configured Alert Triggers
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {[50, 75, 90, 100].map((threshold) => {
                            const isConfigured = (b.threshold_percents || []).includes(threshold);
                            const hasTriggered = b.recent_alerts?.some(a => a.threshold_percent === threshold);
                            return (
                              <span
                                key={threshold}
                                className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-semibold flex items-center gap-1 ${
                                  hasTriggered
                                    ? 'bg-red-500/10 text-red-400 border border-red-500/30'
                                    : isConfigured
                                    ? 'bg-slate-800 text-slate-300 border border-slate-700'
                                    : 'bg-slate-950 text-slate-600 border border-slate-900 line-through'
                                }`}
                              >
                                {threshold}% Cap
                                {hasTriggered && <AlertTriangle className="h-3 w-3 text-red-400" />}
                              </span>
                            );
                          })}
                        </div>
                      </div>

                      {/* Notification Recipients */}
                      <div className="pt-3 border-t border-slate-800/80 mb-4">
                        <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                          Alert Notification Targets
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {b.alert_recipients && b.alert_recipients.length > 0 ? (
                            b.alert_recipients.map((rec, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 rounded text-[11px] bg-slate-800 border border-slate-700 text-slate-300 flex items-center gap-1 font-mono"
                              >
                                <span className="uppercase text-[9px] text-brand-400 font-bold">{rec.channel}:</span>
                                {rec.target}
                              </span>
                            ))
                          ) : (
                            <span className="text-slate-500 text-xs italic">No recipients registered</span>
                          )}
                        </div>
                      </div>

                      {/* Recent Alert Audit Log */}
                      {b.recent_alerts && b.recent_alerts.length > 0 && (
                        <div className="pt-3 border-t border-slate-800/80 space-y-2">
                          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                            Recent Dispatches
                          </div>
                          <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                            {b.recent_alerts.map((alert) => (
                              <div
                                key={alert.id}
                                className="p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-[11px]"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-red-400 font-bold">{alert.threshold_percent}%</span>
                                  <span className="text-slate-300 font-mono">₹{alert.current_spend.toLocaleString()}</span>
                                  <span className="text-slate-500">via {alert.notification_channel}</span>
                                </div>
                                <span className="text-[10px] text-slate-500 font-mono">
                                  {new Date(alert.triggered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 9: ADMIN PRICING & AUDITING CONSOLE */}
      {activeTab === 'admin' && (
        <div className="space-y-6">
          {/* Admin Header Action Card */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
            <div>
              <div className="flex items-center gap-2">
                <span className="p-1 rounded-md bg-brand-500/10 text-brand-400">
                  <ShieldCheck className="h-5 w-5" />
                </span>
                <h2 className="text-base font-bold text-white">
                  Administrative Pricing Governance & Audit Console
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 uppercase tracking-wide">
                  Admin Privileged
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Configure commercial tier rates, publish versioned schedules for future periods, provision bespoke enterprise agreements, and review immutable audit logs.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => handleOpenAdjustmentModal()}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition flex items-center gap-1.5"
              >
                <DollarSign className="h-3.5 w-3.5 text-emerald-400" />
                Apply Credit Adjustment
              </button>
              <button
                onClick={handleOpenCustomAgreementModal}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 shadow-lg shadow-brand-500/20 transition flex items-center gap-1.5"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Provision Enterprise Agreement
              </button>
            </div>
          </div>

          {/* Section 1: Tier Rate Schedules & Version Management */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-200">
                  Commercial Subscription Tiers & Pricing Versions
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Publishing a new pricing version takes effect for future billing periods without altering past invoices.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {(adminPlans.length > 0 ? adminPlans : plans).map((plan) => {
                const activeVersion = plan.active_pricing || (plan.pricing_versions && plan.pricing_versions[plan.pricing_versions.length - 1]);
                const versionsCount = plan.pricing_versions ? plan.pricing_versions.length : 1;

                return (
                  <div
                    key={plan.id}
                    className="p-6 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col justify-between space-y-5 hover:border-slate-700 transition"
                  >
                    <div>
                      {/* Plan Header */}
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-base font-bold text-white">{plan.name}</h4>
                            {plan.is_custom && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                Bespoke
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-slate-400 font-mono block mt-0.5">{plan.plan_code}</span>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                          Tier {plan.tier_level}
                        </span>
                      </div>

                      {/* Active Version Rates */}
                      <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2 mb-4">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400">Current Schedule:</span>
                          <span className="font-mono text-emerald-400 font-bold">
                            Version {activeVersion ? activeVersion.version_number : 1}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400">Monthly Base Price:</span>
                          <span className="font-mono text-white font-bold text-sm">
                            ₹{activeVersion ? Math.round(activeVersion.monthly_base_price).toLocaleString() : 'N/A'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-400">Included Allowance:</span>
                          <span className="font-mono text-blue-400 font-bold">
                            {activeVersion ? activeVersion.included_pipeline_runs.toLocaleString() : '0'} runs/mo
                          </span>
                        </div>
                        <div className="pt-2 border-t border-slate-800 space-y-1 text-[11px]">
                          <div className="flex justify-between text-slate-400">
                            <span>Basic (2-5 acts):</span>
                            <span className="font-mono text-white">₹{activeVersion?.basic_run_rate || '0.50'}</span>
                          </div>
                          <div className="flex justify-between text-slate-400">
                            <span>Standard (6-15 acts):</span>
                            <span className="font-mono text-white">₹{activeVersion?.standard_run_rate || '1.50'}</span>
                          </div>
                          <div className="flex justify-between text-slate-400">
                            <span>Advanced (16-30 acts):</span>
                            <span className="font-mono text-white">₹{activeVersion?.advanced_run_rate || '3.00'}</span>
                          </div>
                          <div className="flex justify-between text-slate-400">
                            <span>Spark Worker Hour:</span>
                            <span className="font-mono text-brand-400">₹{activeVersion?.spark_node_hour_rate || '45.00'}/hr</span>
                          </div>
                        </div>
                      </div>

                      {/* Historical Version Count */}
                      <div className="text-[11px] text-slate-500 flex items-center justify-between">
                        <span>{versionsCount} historical schedule{versionsCount > 1 ? 's' : ''} stored</span>
                        <span className="text-slate-400 font-mono">Immutable</span>
                      </div>
                    </div>

                    {/* Action Button */}
                    <button
                      onClick={() => handleOpenPublishVersionModal(plan)}
                      className="w-full py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs border border-slate-700 transition flex items-center justify-center gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Publish New Pricing Version
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 2: Invoice Credit & Goodwill Adjustments */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-emerald-400" />
                  Manual Invoice Credit & Goodwill Adjustments
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Apply administrative credit deductions or SLA goodwill waivers to customer invoices with full audit justification.
                </p>
              </div>
              <button
                onClick={() => handleOpenAdjustmentModal()}
                className="px-3.5 py-1.5 rounded-xl text-xs font-semibold text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 transition flex items-center gap-1.5"
              >
                <Plus className="h-3.5 w-3.5" />
                Add Credit Adjustment
              </button>
            </div>

            {invoices.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-2">No generated invoices available for adjustments.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-mono text-[11px]">
                    <tr>
                      <th className="py-2.5 px-3">Invoice #</th>
                      <th className="py-2.5 px-3">Period</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Subtotal</th>
                      <th className="py-2.5 px-3">Adjustments</th>
                      <th className="py-2.5 px-3">Total (Incl. Tax)</th>
                      <th className="py-2.5 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {invoices.slice(0, 5).map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-3 font-bold text-white">{inv.invoice_number}</td>
                        <td className="py-2.5 px-3 text-slate-400">{inv.period_key}</td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-semibold ${
                            inv.status === 'Paid'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}>
                            {inv.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-300">₹{Number(inv.subtotal_amount).toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-rose-400">
                          {Number(inv.adjustments_amount) > 0 ? `-₹${Number(inv.adjustments_amount).toLocaleString()}` : '₹0.00'}
                        </td>
                        <td className="py-2.5 px-3 font-bold text-brand-400">₹{Number(inv.total_amount).toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-right font-sans">
                          {inv.status !== 'Paid' && inv.status !== 'Void' ? (
                            <button
                              onClick={() => handleOpenAdjustmentModal(inv.id)}
                              className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
                            >
                              Apply Credit
                            </button>
                          ) : (
                            <span className="text-[11px] text-slate-500 italic">Locked</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Section 3: Immutable Billing Audit Trail */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-brand-400" />
                  Immutable Billing Governance Audit Log
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Cryptographically track all administrative price changes, volume overrides, credits, and commercial mutations.
                </p>
              </div>
              <button
                onClick={fetchData}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition flex items-center gap-1.5"
              >
                <RefreshCw className="h-3 w-3" />
                Refresh Audit Trail
              </button>
            </div>

            {auditLogs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs italic">
                No billing audit logs recorded yet. Administrative changes will automatically populate here.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-mono text-[11px]">
                    <tr>
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3">Admin</th>
                      <th className="py-2.5 px-3">Action</th>
                      <th className="py-2.5 px-3">Resource</th>
                      <th className="py-2.5 px-3">Justification</th>
                      <th className="py-2.5 px-3 text-right">Diff Inspector</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                          {new Date(log.created_at).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="py-2.5 px-3 text-white font-sans">{log.admin_email || log.admin_user_id.slice(0, 8)}</td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-semibold ${
                            log.action === 'UpdatePricingVersion'
                              ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                              : log.action === 'ConfigureCustomAgreement'
                              ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                              : log.action === 'ApplyCredit'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-300">
                          {log.resource_type} <span className="text-slate-500 text-[10px]">({log.resource_id?.slice(0, 8)})</span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 font-sans max-w-xs truncate" title={log.justification}>
                          {log.justification}
                        </td>
                        <td className="py-2.5 px-3 text-right font-sans">
                          <button
                            onClick={() => setSelectedAuditLogForDiff(log)}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-brand-400 border border-slate-700 transition"
                          >
                            Inspect State Diff
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Slide-Over Drawer: Usage Breakdown Details */}
      {selectedRunForDrawer && (
        <div className="fixed inset-0 z-50 overflow-hidden flex justify-end bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col h-full animate-in slide-in-from-right duration-300">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-800 flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="p-1.5 rounded-lg bg-brand-500/10 text-brand-400">
                    <Layers className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-bold text-white truncate max-w-[280px]">
                    {selectedRunForDrawer.pipeline_name}
                  </h3>
                </div>
                <div className="flex items-center gap-2 mt-2 text-[11px] text-slate-400 font-mono">
                  <span>Run ID: {selectedRunForDrawer.pipeline_run_id}</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(selectedRunForDrawer.pipeline_run_id);
                      alert('Copied Run ID to clipboard!');
                    }}
                    className="hover:text-white"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </div>
              </div>

              <button
                onClick={() => setSelectedRunForDrawer(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
              {/* Badges Bar */}
              <div className="flex flex-wrap items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                  selectedRunForDrawer.execution_status === 'Succeeded' || selectedRunForDrawer.execution_status === 'Completed'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}>
                  {selectedRunForDrawer.execution_status}
                </span>

                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {selectedRunForDrawer.execution_engine}
                </span>

                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {selectedRunForDrawer.classification} ({selectedRunForDrawer.activity_count} activities)
                </span>
              </div>

              {/* Execution Telemetry Grid */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2.5">
                <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Execution Telemetry
                </h4>
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <span className="text-slate-500 block text-[10px]">Execution Duration</span>
                    <span className="text-white font-mono font-medium">{Number(selectedRunForDrawer.duration_seconds).toFixed(2)}s</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Started At</span>
                    <span className="text-white font-mono text-[11px]">
                      {new Date(selectedRunForDrawer.started_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Rows Processed</span>
                    <span className="text-white font-mono">{selectedRunForDrawer.rows_processed?.toLocaleString() || 0}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Bytes Moved</span>
                    <span className="text-white font-mono">{((selectedRunForDrawer.bytes_processed || 0) / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                </div>
              </div>

              {/* Billability Evaluation Card */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    Billability Status & Determination
                  </h4>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    selectedRunForDrawer.is_billable
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}>
                    {selectedRunForDrawer.is_billable ? 'Billable Run' : 'Non-Billable'}
                  </span>
                </div>

                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {selectedRunForDrawer.is_billable
                    ? 'Execution commenced on customer instruction. Standard complexity rate applied under active commercial subscription agreement.'
                    : `Execution exempted from orchestration billing. Reason: ${selectedRunForDrawer.non_billable_reason || 'PlatformSystemError or Pre-start cancellation'}.`}
                </p>
              </div>

              {/* Financial Calculation Breakdown */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2.5">
                <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Itemized Financial Breakdown
                </h4>
                <div className="space-y-1.5 pt-1">
                  <div className="flex justify-between text-slate-300">
                    <span>Applicable Complexity Tier:</span>
                    <span className="font-mono text-white">{selectedRunForDrawer.classification}</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Base Tier Rate:</span>
                    <span className="font-mono text-white">
                      ₹{selectedRunForDrawer.classification === 'Basic' ? '0.50' : selectedRunForDrawer.classification === 'Standard' ? '1.50' : selectedRunForDrawer.classification === 'Advanced' ? '3.00' : '5.00'}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Monthly Allowance Status:</span>
                    <span className="font-mono text-emerald-400">Included / Metered</span>
                  </div>
                  <div className="flex justify-between text-white font-bold pt-2 border-t border-slate-800">
                    <span>Calculated Run Surcharge:</span>
                    <span className="font-mono text-brand-400 text-sm">
                      ₹{Number(selectedRunForDrawer.calculated_charge).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-4 border-t border-slate-800 flex items-center justify-between gap-3 bg-slate-950/50">
              <button
                onClick={() => handleOverrideBillability(selectedRunForDrawer.id, selectedRunForDrawer.is_billable)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition flex items-center gap-2"
              >
                <Sliders className="h-3.5 w-3.5" />
                {selectedRunForDrawer.is_billable ? 'Waive Billability' : 'Reinstate Billable'}
              </button>

              <button
                onClick={() => setSelectedRunForDrawer(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* INVOICE DETAILS DRAWER */}
      {selectedInvoice && !isPaymentModalOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/70 backdrop-blur-sm flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    {selectedInvoice.invoice_number}
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                      selectedInvoice.status === 'Paid'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {selectedInvoice.status}
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Period: {selectedInvoice.period_key} • Issued: {new Date(selectedInvoice.issue_date).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedInvoice(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 flex-1 overflow-y-auto space-y-5 text-xs">
              {/* Metadata Card */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 grid grid-cols-2 gap-3">
                <div>
                  <span className="text-slate-500 block text-[10px]">Due Date</span>
                  <span className="text-white font-mono">{new Date(selectedInvoice.due_date).toLocaleDateString()}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Currency</span>
                  <span className="text-white font-mono">{selectedInvoice.currency}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Subtotal (Pre-Tax)</span>
                  <span className="text-white font-mono">₹{Number(selectedInvoice.subtotal_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">GST (18.0%)</span>
                  <span className="text-brand-400 font-mono">₹{Number(selectedInvoice.tax_amount).toFixed(2)}</span>
                </div>
              </div>

              {/* Itemized Line Items */}
              <div className="space-y-2">
                <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Itemized Charges & Allowance Allocation
                </h4>
                <div className="rounded-xl border border-slate-800 overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/70 border-b border-slate-800 text-[10px] text-slate-400 uppercase">
                      <tr>
                        <th className="py-2 px-3">Description</th>
                        <th className="py-2 px-2 text-right">Qty</th>
                        <th className="py-2 px-2 text-right">Rate</th>
                        <th className="py-2 px-3 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {(selectedInvoice.line_items || []).map((li, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/20">
                          <td className="py-2.5 px-3 font-sans text-slate-200">
                            <span className="block font-medium">{li.description}</span>
                            <span className="text-[10px] text-slate-500">{li.item_type}</span>
                          </td>
                          <td className="py-2.5 px-2 text-right text-slate-300">{Number(li.quantity).toLocaleString()}</td>
                          <td className="py-2.5 px-2 text-right text-slate-400">₹{Number(li.unit_price).toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right text-white font-semibold">₹{Number(li.amount).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Payments History */}
              {selectedInvoice.payments && selectedInvoice.payments.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    Recorded Payment Receipts
                  </h4>
                  <div className="space-y-2">
                    {selectedInvoice.payments.map((p) => (
                      <div key={p.id} className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 flex items-center justify-between">
                        <div>
                          <div className="font-mono text-emerald-400 font-semibold text-xs flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {p.payment_reference}
                          </div>
                          <p className="text-[10px] text-slate-400 mt-0.5">
                            Method: {p.payment_method} • Verified on {new Date(p.payment_date).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="text-right">
                          <span className="font-mono text-white font-bold text-xs">₹{Number(p.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                          <span className="block text-[10px] text-emerald-400">{p.payment_status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-800 flex items-center justify-between gap-3 bg-slate-950/60">
              <button
                onClick={() => handleDownloadInvoicePDF(selectedInvoice.id, selectedInvoice.invoice_number)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 transition flex items-center gap-2"
              >
                <Download className="h-3.5 w-3.5" />
                Download Official PDF
              </button>

              {selectedInvoice.status !== 'Paid' && (
                <button
                  onClick={() => setIsPaymentModalOpen(true)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 transition shadow-lg shadow-brand-500/20"
                >
                  Record Payment Wire
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* RECORD PAYMENT MODAL */}
      {isPaymentModalOpen && selectedInvoice && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-brand-400" />
                Record Offline Payment Remittance
              </h3>
              <button
                onClick={() => setIsPaymentModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Invoice Number</label>
                <input
                  type="text"
                  disabled
                  value={selectedInvoice.invoice_number}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-mono cursor-not-allowed"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Amount to Record (INR)</label>
                <input
                  type="number"
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Payment Reference / UTR Number</label>
                <input
                  type="text"
                  value={paymentRef}
                  onChange={(e) => setPaymentRef(e.target.value)}
                  placeholder="e.g. UTR-2026110901 or PO-45091"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Remittance Method</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:border-brand-500 focus:outline-none"
                >
                  <option value="BankTransfer">Bank Wire (NEFT / RTGS / IMPS)</option>
                  <option value="CorporatePO">Corporate Purchase Order</option>
                  <option value="DirectDebit">Direct ACH / NetBanking</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Audit Notes / Verification Justification</label>
                <textarea
                  value={paymentNotes}
                  onChange={(e) => setPaymentNotes(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end gap-3 bg-slate-950/50">
              <button
                onClick={() => setIsPaymentModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                onClick={handleRecordPayment}
                disabled={isRecordingPayment || !paymentAmount || !paymentRef}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
              >
                {isRecordingPayment ? 'Recording...' : 'Confirm Verified Payment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE / EDIT BUDGET MODAL */}
      {isBudgetModalOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Target className="h-4 w-4 text-brand-400" />
                {editingBudget ? 'Edit Budget Policy' : 'Create Budget Control Policy'}
              </h3>
              <button
                onClick={() => setIsBudgetModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs max-h-[75vh] overflow-y-auto">
              <div>
                <label className="text-slate-400 block mb-1">Policy Name</label>
                <input
                  type="text"
                  value={budgetFormName}
                  onChange={(e) => setBudgetFormName(e.target.value)}
                  placeholder="e.g. Production Monthly Spend Cap"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1">Monthly Spending Cap (INR)</label>
                  <input
                    type="number"
                    value={budgetFormSpendLimit}
                    onChange={(e) => setBudgetFormSpendLimit(e.target.value)}
                    placeholder="25000"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                  <span className="text-[10px] text-slate-500 mt-0.5 block">0 = Uncapped spend</span>
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Monthly Run Count Limit</label>
                  <input
                    type="number"
                    value={budgetFormRunLimit}
                    onChange={(e) => setBudgetFormRunLimit(e.target.value)}
                    placeholder="10000"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                  <span className="text-[10px] text-slate-500 mt-0.5 block">0 = Uncapped runs</span>
                </div>
              </div>

              {/* Hard Limit Toggle */}
              <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-amber-400" />
                    <span className="font-semibold text-white">Enforce Hard Execution Limit</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={budgetFormHardLimit}
                    onChange={(e) => setBudgetFormHardLimit(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-700 text-brand-600 focus:ring-brand-500"
                  />
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  When enabled, pipeline runs will be automatically blocked upon reaching 100% of spending cap or run limit. 
                  When disabled (default), DataForge operates in warn-only mode, dispatching alerts without disrupting workloads.
                </p>
              </div>

              {/* Alert Thresholds */}
              <div>
                <label className="text-slate-400 block mb-1.5">Alert Trigger Thresholds</label>
                <div className="grid grid-cols-4 gap-2">
                  {[50, 75, 90, 100].map((pct) => (
                    <button
                      type="button"
                      key={pct}
                      onClick={() => handleToggleThreshold(pct)}
                      className={`py-2 px-3 rounded-lg border font-mono text-xs font-semibold transition ${
                        budgetFormThresholds.includes(pct)
                          ? 'bg-brand-600/20 border-brand-500 text-brand-300'
                          : 'bg-slate-950 border-slate-800 text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      {pct}%
                    </button>
                  ))}
                </div>
              </div>

              {/* Notification Recipients */}
              <div className="space-y-2">
                <label className="text-slate-400 block">Notification Channels & Recipients</label>
                
                {/* Add Recipient Row */}
                <div className="flex items-center gap-2">
                  <select
                    value={recipientChannel}
                    onChange={(e: any) => setRecipientChannel(e.target.value)}
                    className="w-28 px-2 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs focus:border-brand-500 focus:outline-none"
                  >
                    <option value="email">Email</option>
                    <option value="slack">Slack</option>
                    <option value="webhook">Webhook</option>
                  </select>
                  <input
                    type="text"
                    value={recipientTarget}
                    onChange={(e) => setRecipientTarget(e.target.value)}
                    placeholder={recipientChannel === 'email' ? 'ops@company.com' : recipientChannel === 'slack' ? '#data-alerts' : 'https://api.internal/hook'}
                    className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleAddRecipient}
                    disabled={!recipientTarget.trim()}
                    className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs disabled:opacity-50"
                  >
                    Add
                  </button>
                </div>

                {/* Recipient Pills */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {budgetFormRecipients.map((rec, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[11px] flex items-center gap-1.5"
                    >
                      <span className="text-[9px] uppercase font-bold text-brand-400">{rec.channel}:</span>
                      <span className="font-mono">{rec.target}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveRecipient(idx)}
                        className="text-slate-500 hover:text-red-400 ml-1"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end gap-3 bg-slate-950/50">
              <button
                type="button"
                onClick={() => setIsBudgetModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveBudget}
                disabled={isSavingBudget || !budgetFormName.trim()}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 transition shadow-lg shadow-brand-500/20 disabled:opacity-50 flex items-center gap-1.5"
              >
                {isSavingBudget ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save Budget Policy'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PUBLISH PRICING VERSION MODAL */}
      {isPublishModalOpen && selectedPlanForVersion && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Plus className="h-4 w-4 text-brand-400" />
                  Publish New Pricing Version Schedule
                </h3>
                <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
                  Plan: {selectedPlanForVersion.name} ({selectedPlanForVersion.plan_code})
                </span>
              </div>
              <button
                onClick={() => setIsPublishModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs max-h-[75vh] overflow-y-auto">
              <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-300 text-[11px] leading-relaxed">
                Publishing this version creates an immutable rate record effective for future billing cycles. Past and already generated invoices are never retroactively modified.
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1">Monthly Base Price (INR)</label>
                  <input
                    type="number"
                    value={pubMonthlyPrice}
                    onChange={(e) => setPubMonthlyPrice(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Annual Base Price (INR)</label>
                  <input
                    type="number"
                    value={pubAnnualPrice}
                    onChange={(e) => setPubAnnualPrice(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1">Included Monthly Runs</label>
                  <input
                    type="number"
                    value={pubIncludedRuns}
                    onChange={(e) => setPubIncludedRuns(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Spark Node-Hour Rate (INR)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={pubSparkRate}
                    onChange={(e) => setPubSparkRate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Overage Rates */}
              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
                <span className="font-semibold text-white block">Additional Overage Rates Per Execution</span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div>
                    <label className="text-slate-500 block text-[10px] mb-0.5">Basic (2-5 acts)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={pubBasicRate}
                      onChange={(e) => setPubBasicRate(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-500 block text-[10px] mb-0.5">Standard (6-15 acts)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={pubStandardRate}
                      onChange={(e) => setPubStandardRate(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-500 block text-[10px] mb-0.5">Advanced (16-30 acts)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={pubAdvancedRate}
                      onChange={(e) => setPubAdvancedRate(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-500 block text-[10px] mb-0.5">Complex (31+ acts)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={pubComplexRate}
                      onChange={(e) => setPubComplexRate(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">
                  Administrative Justification <span className="text-rose-400">*</span>
                </label>
                <textarea
                  value={pubJustification}
                  onChange={(e) => setPubJustification(e.target.value)}
                  rows={2}
                  placeholder="e.g. Approved tier pricing update per Board of Directors Q2 financial plan"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end gap-3 bg-slate-950/50">
              <button
                type="button"
                onClick={() => setIsPublishModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePublishPricingVersion}
                disabled={isPublishingVersion || !pubJustification.trim()}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 transition shadow-lg shadow-brand-500/20 disabled:opacity-50 flex items-center gap-1.5"
              >
                {isPublishingVersion ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Publishing...
                  </>
                ) : (
                  'Publish Version Schedule'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BESPOKE ENTERPRISE AGREEMENT MODAL */}
      {isCustomAgreementModalOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-400" />
                Provision Bespoke Enterprise Agreement
              </h3>
              <button
                onClick={() => setIsCustomAgreementModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs max-h-[75vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1">Target Tenant ID</label>
                  <input
                    type="text"
                    value={customTenantId}
                    onChange={(e) => setCustomTenantId(e.target.value)}
                    placeholder="Enter Tenant UUID"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Agreement Name</label>
                  <input
                    type="text"
                    value={customPlanName}
                    onChange={(e) => setCustomPlanName(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1">Negotiated Monthly Base Price (INR)</label>
                  <input
                    type="number"
                    value={customMonthlyPrice}
                    onChange={(e) => setCustomMonthlyPrice(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Negotiated Included Runs</label>
                  <input
                    type="number"
                    value={customIncludedRuns}
                    onChange={(e) => setCustomIncludedRuns(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-slate-500 block text-[10px] mb-0.5">Basic (₹/run)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={customBasicRate}
                    onChange={(e) => setCustomBasicRate(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-500 block text-[10px] mb-0.5">Standard (₹/run)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={customStandardRate}
                    onChange={(e) => setCustomStandardRate(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-500 block text-[10px] mb-0.5">Spark Rate (₹/hr)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={customSparkRate}
                    onChange={(e) => setCustomSparkRate(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Contract & Dedicated SLA Notes</label>
                <textarea
                  value={customNotes}
                  onChange={(e) => setCustomNotes(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">
                  Administrative Justification <span className="text-rose-400">*</span>
                </label>
                <textarea
                  value={customJustification}
                  onChange={(e) => setCustomJustification(e.target.value)}
                  rows={2}
                  placeholder="e.g. Multi-year enterprise license signed with VP Commercial"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end gap-3 bg-slate-950/50">
              <button
                type="button"
                onClick={() => setIsCustomAgreementModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveCustomAgreement}
                disabled={isSavingCustomAgreement || !customTenantId.trim() || !customJustification.trim()}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 transition shadow-lg shadow-purple-500/20 disabled:opacity-50 flex items-center gap-1.5"
              >
                {isSavingCustomAgreement ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Provisioning...
                  </>
                ) : (
                  'Bind Enterprise Contract'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MANUAL INVOICE CREDIT / ADJUSTMENT MODAL */}
      {isAdjustmentModalOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-emerald-400" />
                Apply Invoice Credit Adjustment
              </h3>
              <button
                onClick={() => setIsAdjustmentModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Target Invoice</label>
                <select
                  value={adjInvoiceId}
                  onChange={(e) => setAdjInvoiceId(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs focus:border-brand-500 focus:outline-none"
                >
                  <option value="">Select Invoice...</option>
                  {invoices.filter(i => i.status !== 'Paid' && i.status !== 'Void').map(i => (
                    <option key={i.id} value={i.id}>
                      {i.invoice_number} ({i.period_key}) - ₹{Number(i.total_amount).toLocaleString()}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1">Adjustment Type</label>
                  <select
                    value={adjType}
                    onChange={(e) => setAdjType(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs focus:border-brand-500 focus:outline-none"
                  >
                    <option value="GoodwillSLA">Goodwill SLA Waiver</option>
                    <option value="Discount">Contractual Discount</option>
                    <option value="Credit">Billing Error Credit</option>
                    <option value="Refund">Direct Credit Refund</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Credit Amount (INR)</label>
                  <input
                    type="number"
                    value={adjAmount}
                    onChange={(e) => setAdjAmount(e.target.value)}
                    placeholder="2000"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Line Item Description</label>
                <input
                  type="text"
                  value={adjDesc}
                  onChange={(e) => setAdjDesc(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">
                  Administrative Justification <span className="text-rose-400">*</span>
                </label>
                <textarea
                  value={adjJustification}
                  onChange={(e) => setAdjJustification(e.target.value)}
                  rows={2}
                  placeholder="e.g. Outage incident INC-4902 credit approved by Head of Customer Success"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end gap-3 bg-slate-950/50">
              <button
                type="button"
                onClick={() => setIsAdjustmentModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApplyAdjustment}
                disabled={isApplyingAdjustment || !adjInvoiceId || !adjAmount || !adjJustification.trim()}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 transition shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center gap-1.5"
              >
                {isApplyingAdjustment ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Applying...
                  </>
                ) : (
                  'Apply Credit to Invoice'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AUDIT STATE DIFF INSPECTOR MODAL */}
      {selectedAuditLogForDiff && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-brand-400" />
                  Audit State Diff Inspector: {selectedAuditLogForDiff.action}
                </h3>
                <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
                  Resource: {selectedAuditLogForDiff.resource_type} • ID: {selectedAuditLogForDiff.resource_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedAuditLogForDiff(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs max-h-[75vh] overflow-y-auto">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Administrative Justification</span>
                <p className="text-slate-200">{selectedAuditLogForDiff.justification}</p>
                <span className="text-[10px] text-slate-500 block pt-1 font-mono">
                  Recorded on {new Date(selectedAuditLogForDiff.created_at).toLocaleString()} by {selectedAuditLogForDiff.admin_email || selectedAuditLogForDiff.admin_user_id}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-[11px] font-bold text-amber-400 mb-1.5 block">State Prior to Mutation (Before)</span>
                  <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[10px] text-slate-300 overflow-x-auto max-h-60">
                    {JSON.stringify(selectedAuditLogForDiff.before_state, null, 2)}
                  </pre>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-emerald-400 mb-1.5 block">Mutated State Applied (After)</span>
                  <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[10px] text-emerald-300 overflow-x-auto max-h-60">
                    {JSON.stringify(selectedAuditLogForDiff.after_state, null, 2)}
                  </pre>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 flex justify-end bg-slate-950/50">
              <button
                type="button"
                onClick={() => setSelectedAuditLogForDiff(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 transition border border-slate-700"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
