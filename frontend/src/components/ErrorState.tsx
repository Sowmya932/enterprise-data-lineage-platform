interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

function ErrorState({ message, onRetry }: ErrorStateProps): JSX.Element {
  return (
    <div className="state-box state-error" role="alert">
      <h3>Request failed</h3>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="button-secondary" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export default ErrorState;
