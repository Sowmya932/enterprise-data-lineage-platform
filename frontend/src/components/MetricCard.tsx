interface MetricCardProps {
  title: string;
  value: number;
  accent: 'teal' | 'amber' | 'coral' | 'blue';
  subtitle?: string;
}

function MetricCard({ title, value, accent, subtitle }: MetricCardProps): JSX.Element {
  return (
    <article className={`metric-card metric-${accent}`}>
      <p>{title}</p>
      <strong>{value.toLocaleString()}</strong>
      {subtitle ? <small>{subtitle}</small> : null}
    </article>
  );
}

export default MetricCard;
