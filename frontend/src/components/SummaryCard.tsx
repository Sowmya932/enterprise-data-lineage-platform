interface SummaryCardProps {
  title: string;
  value: number;
  accent: 'teal' | 'amber' | 'coral' | 'blue';
}

function SummaryCard({ title, value, accent }: SummaryCardProps): JSX.Element {
  return (
    <article className={`summary-card summary-${accent}`}>
      <p>{title}</p>
      <strong>{value.toLocaleString()}</strong>
    </article>
  );
}

export default SummaryCard;
