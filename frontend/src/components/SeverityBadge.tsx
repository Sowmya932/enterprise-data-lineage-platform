import { Chip } from '@mui/material';

export type SeverityLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

interface SeverityBadgeProps {
  severity: string;
  compact?: boolean;
}

const severityStyles: Record<SeverityLevel, { label: string; bg: string; color: string }> = {
  NONE: { label: 'NONE', bg: '#eceff3', color: '#374151' },
  LOW: { label: 'LOW', bg: '#e8f5e9', color: '#1b5e20' },
  MEDIUM: { label: 'MEDIUM', bg: '#fff7e6', color: '#8d5f00' },
  HIGH: { label: 'HIGH', bg: '#ffe8d9', color: '#ad3f0d' },
  CRITICAL: { label: 'CRITICAL', bg: '#ffebee', color: '#8b1326' },
};

function normalizeSeverity(value: string): SeverityLevel {
  const upper = value.toUpperCase();
  if (upper in severityStyles) {
    return upper as SeverityLevel;
  }
  return 'NONE';
}

function SeverityBadge({ severity, compact = false }: SeverityBadgeProps): JSX.Element {
  const normalized = normalizeSeverity(severity);
  const style = severityStyles[normalized];

  return (
    <Chip
      label={style.label}
      size={compact ? 'small' : 'medium'}
      sx={{
        backgroundColor: style.bg,
        color: style.color,
        fontWeight: 700,
        letterSpacing: '0.03em',
      }}
    />
  );
}

export default SeverityBadge;
