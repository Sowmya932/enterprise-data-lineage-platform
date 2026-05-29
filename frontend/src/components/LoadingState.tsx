interface LoadingStateProps {
  label?: string;
}

function LoadingState({ label = 'Loading data...' }: LoadingStateProps): JSX.Element {
  return (
    <div className="state-box" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export default LoadingState;
