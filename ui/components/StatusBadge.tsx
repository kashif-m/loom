'use client';

interface StatusBadgeProps {
  status: string;
}

const statusColors: Record<string, string> = {
  open: 'bg-blue-100 text-blue-800 border-blue-200',
  blocked: 'bg-amber-100 text-amber-800 border-amber-200',
  escalated: 'bg-red-100 text-red-800 border-red-200',
  closed: 'bg-green-100 text-green-800 border-green-200',
  draft: 'bg-gray-100 text-gray-800 border-gray-200',
  active: 'bg-green-100 text-green-800 border-green-200',
  deprecated: 'bg-gray-100 text-gray-800 border-gray-200',
};

const statusLabels: Record<string, string> = {
  open: 'Open',
  blocked: 'Blocked',
  escalated: 'Needs your input',
  closed: 'Closed',
  draft: 'Draft',
  active: 'Active',
  deprecated: 'Deprecated',
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colorClass = statusColors[status] || statusColors.open;
  const label = statusLabels[status] || status;

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
      {label}
    </span>
  );
}
