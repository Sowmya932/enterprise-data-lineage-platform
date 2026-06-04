import { Component, ErrorInfo, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { logger } from '../services/logger';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    logger.error('Unhandled UI error', {
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
    });
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="state-box state-error" role="alert">
          <h3>Something went wrong</h3>
          <p>The interface hit an unexpected error. Refresh or return to dashboard.</p>
          <Link className="button-link" to="/dashboard">
            Go to Dashboard
          </Link>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
