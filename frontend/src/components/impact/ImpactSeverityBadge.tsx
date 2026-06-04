import SeverityBadge from '../SeverityBadge';

interface ImpactSeverityBadgeProps {
  severity: string;
  compact?: boolean;
}

function ImpactSeverityBadge({ severity, compact = false }: ImpactSeverityBadgeProps): JSX.Element {
  return <SeverityBadge severity={severity} compact={compact} />;
}

export default ImpactSeverityBadge;
