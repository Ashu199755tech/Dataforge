import React from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertTriangle, 
  Activity, 
  ShieldCheck, 
  PauseCircle, 
  MinusCircle,
  HelpCircle,
  Sparkles
} from 'lucide-react';

export type EntityStatus = 
  // Pipeline & Activity Run statuses
  | 'Succeeded' 
  | 'Failed' 
  | 'Running' 
  | 'In Progress' 
  | 'Pending' 
  | 'Queued' 
  | 'Cancelled' 
  | 'Skipped'
  // Runtime statuses
  | 'Online' 
  | 'Offline' 
  | 'Registering' 
  | 'Disabled'
  // Dataset statuses
  | 'Current' 
  | 'DriftDetected' 
  | 'NeedsSync'
  // Connection statuses
  | 'Verified' 
  | 'Active' 
  | 'Degraded'
  // Deployment statuses
  | 'PendingApproval' 
  | 'Approved' 
  | 'Rejected' 
  | 'Deployed' 
  | 'RolledBack';

interface StatusBadgeProps {
  status: EntityStatus | string;
  size?: 'sm' | 'md';
  showIcon?: boolean;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'sm',
  showIcon = true,
  className = ''
}) => {
  const norm = (status || '').toLowerCase().trim();

  let config = {
    label: status,
    bg: 'bg-slate-800',
    text: 'text-slate-300',
    border: 'border-slate-700',
    icon: HelpCircle,
    pulse: false
  };

  switch (norm) {
    case 'succeeded':
    case 'online':
    case 'current':
    case 'verified':
    case 'active':
    case 'deployed':
      config = {
        label: status === 'Current' ? 'Schema Current' : status,
        bg: 'bg-emerald-500/10',
        text: 'text-emerald-400',
        border: 'border-emerald-500/25',
        icon: CheckCircle2,
        pulse: false
      };
      break;

    case 'failed':
    case 'offline':
    case 'rejected':
      config = {
        label: status,
        bg: 'bg-rose-500/10',
        text: 'text-rose-400',
        border: 'border-rose-500/25',
        icon: XCircle,
        pulse: false
      };
      break;

    case 'running':
    case 'in progress':
      config = {
        label: status,
        bg: 'bg-brand-500/10',
        text: 'text-brand-400',
        border: 'border-brand-500/30',
        icon: Clock,
        pulse: true
      };
      break;

    case 'driftdetected':
    case 'degraded':
    case 'needssync':
    case 'warning':
      config = {
        label: norm === 'driftdetected' ? 'Drift Detected' : status,
        bg: 'bg-amber-500/10',
        text: 'text-amber-400',
        border: 'border-amber-500/30',
        icon: AlertTriangle,
        pulse: false
      };
      break;

    case 'pendingapproval':
    case 'queued':
    case 'pending':
    case 'registering':
      config = {
        label: norm === 'pendingapproval' ? 'Pending Approval' : status,
        bg: 'bg-indigo-500/10',
        text: 'text-indigo-400',
        border: 'border-indigo-500/30',
        icon: Clock,
        pulse: false
      };
      break;

    case 'cancelled':
    case 'disabled':
    case 'skipped':
    case 'rolledback':
      config = {
        label: norm === 'rolledback' ? 'Rolled Back' : status,
        bg: 'bg-slate-800/80',
        text: 'text-slate-400',
        border: 'border-slate-700/60',
        icon: MinusCircle,
        pulse: false
      };
      break;
  }

  const Icon = config.icon;
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';
  const iconSize = size === 'sm' ? 'h-2.5 w-2.5' : 'h-3.5 w-3.5';

  return (
    <span 
      className={`inline-flex items-center gap-1.5 rounded-full font-medium border select-none transition-colors ${config.bg} ${config.text} ${config.border} ${sizeClasses} ${className}`}
    >
      {showIcon && (
        <Icon className={`${iconSize} shrink-0 ${config.pulse ? 'animate-spin' : ''}`} />
      )}
      <span>{config.label}</span>
    </span>
  );
};
