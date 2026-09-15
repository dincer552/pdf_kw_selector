import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  label?: string;
  isMatch?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  isMatch: forcedIsMatch,
  className = '',
  size = 'md',
}) => {
  // Only the actual MATCH result is green. Informational text such as
  // "BA kodu eşleşti" or "PDF2 AHU eşleşti; ..." is still a non-MATCH status.
  const normalizedStatus = status.trim().toUpperCase();
  const isMatch = forcedIsMatch !== undefined ? forcedIsMatch : normalizedStatus === 'MATCH';

  const displayLabel =
    label ||
    (isMatch
      ? 'MATCH'
      : status === 'MISMATCH'
      ? 'MISMATCH'
      : status === 'EBM_PAPST'
      ? 'EBM-PAPST'
      : status === 'ONLY_IN_PDF1'
      ? 'YALNIZCA PDF1'
      : status === 'ONLY_IN_PDF2'
      ? 'YALNIZCA PDF2'
      : status || 'UYUŞMAZLIK');

  const paddingClasses =
    size === 'sm'
      ? 'px-2.5 py-0.5 text-[11px] gap-1'
      : 'px-3 py-0.5 text-[11px] font-bold gap-1.5';

  if (isMatch) {
    return (
      <span
        className={`inline-flex items-center rounded-full font-bold bg-[#dcfce7] border border-[#10b981] text-[#064e3b] shadow-2xs whitespace-nowrap transition-transform ${paddingClasses} ${className}`}
        title="Motor güçleri eşleşti (MATCH)"
      >
        <CheckCircle2 className="w-3.5 h-3.5 text-[#059669] shrink-0" strokeWidth={2.2} />
        <span className="tracking-wider">{displayLabel}</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center rounded-full font-bold bg-[#fee2e2] border border-[#ef4444] text-[#7f1d1d] shadow-2xs whitespace-nowrap transition-transform ${paddingClasses} ${className}`}
      title={`Eşleşme sağlanamadı: ${displayLabel}`}
    >
      <XCircle className="w-3.5 h-3.5 text-[#dc2626] shrink-0" strokeWidth={2.2} />
      <span className="tracking-wider">{displayLabel}</span>
    </span>
  );
};
