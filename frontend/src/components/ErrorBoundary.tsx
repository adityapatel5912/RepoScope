/**
 * ErrorBoundary.tsx
 * Catches any unhandled render error and shows a friendly recovery screen
 * instead of a blank page. Logs with a unique incident ID for triage.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  incidentId: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, incidentId: "" };

  static getDerivedStateFromError(error: Error): State {
    return {
      error,
      incidentId: Math.random().toString(36).slice(2, 10),
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Genuine error — keep console.error
    console.error(
      `[RepoScope incident:${this.state.incidentId}]`,
      error,
      info.componentStack
    );
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleReset = () => {
    this.setState({ error: null, incidentId: "" });
  };

  render() {
    const { error, incidentId } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="w-full h-full flex items-center justify-center bg-bg-base px-6">
        <div className="max-w-md w-full bg-bg-panel border border-border-subtle rounded-2xl shadow-lg p-8 text-center">
          <div className="mx-auto mb-4 w-14 h-14 rounded-2xl bg-gold-50 border border-gold-500/30 flex items-center justify-center">
            <span className="text-2xl">⚠️</span>
          </div>
          <h1 className="text-lg font-semibold text-text-primary mb-1.5">
            Something went wrong
          </h1>
          <p className="text-sm text-text-muted leading-relaxed mb-4">
            RepoScope hit an unexpected error. Your data is safe — reloading
            should fix it.
          </p>
          <p className="text-xs font-mono text-text-muted bg-bg-panel-alt border border-border-subtle rounded-lg px-3 py-2 mb-5 break-all">
            {error.message || "Unknown error"}
          </p>
          <div className="flex items-center justify-center gap-2.5">
            <button
              onClick={this.handleReset}
              className="px-4 py-2 rounded-lg text-sm font-semibold
                bg-bg-panel-alt border border-border-strong text-text-secondary
                hover:bg-bg-panel-hover transition-all duration-200"
            >
              Try again
            </button>
            <button
              onClick={this.handleReload}
              className="px-4 py-2 rounded-lg text-sm font-semibold
                bg-accent-cyan text-white border border-accent-cyan shadow-green
                hover:brightness-105 transition-all duration-200"
            >
              Reload RepoScope
            </button>
          </div>
          <p className="mt-4 text-[10px] text-text-muted font-mono">
            incident: {incidentId}
          </p>
        </div>
      </div>
    );
  }
}
