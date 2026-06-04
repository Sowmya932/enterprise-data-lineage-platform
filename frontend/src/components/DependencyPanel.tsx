interface DependencyPanelProps {
  title: string;
  items: string[];
  emptyLabel: string;
}

function DependencyPanel({ title, items, emptyLabel }: DependencyPanelProps): JSX.Element {
  return (
    <article className="panel dependency-panel">
      <h4>{title}</h4>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="panel-empty-text">{emptyLabel}</p>
      )}
    </article>
  );
}

export default DependencyPanel;
