import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-2xl mx-auto my-12 rounded-panel bg-[#111827] border border-rose-900/60 shadow-xl space-y-4 font-sans text-[#F5F7FB]">
          <div className="flex items-center gap-3 border-b border-[#243149] pb-4">
            <div className="h-10 w-10 rounded-full bg-rose-950/80 border border-rose-700 flex items-center justify-center text-rose-400 font-bold text-lg">
              !
            </div>
            <div>
              <h2 className="text-base font-semibold text-rose-200">
                {this.props.fallbackTitle || "Application Component Recovered"}
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                A rendering issue was caught and contained. Your data and media files remain safe.
              </p>
            </div>
          </div>

          <div className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Diagnostic Detail:
            </div>
            <p className="text-xs font-mono text-rose-300 break-words">
              {this.state.error?.message || "Unknown client runtime error"}
            </p>
          </div>

          {import.meta.env.DEV && this.state.errorInfo && (
            <details className="text-xs font-mono text-slate-400">
              <summary className="cursor-pointer hover:text-slate-200">
                Component Stack Trace (Dev Only)
              </summary>
              <pre className="mt-2 p-2 rounded bg-[#080B12] border border-[#243149] text-[10px] overflow-x-auto text-slate-400">
                {this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={this.handleReset}
              className="px-4 py-2 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono transition-colors"
            >
              Reload View
            </button>
            <button
              type="button"
              onClick={() => {
                this.handleReset();
                window.location.hash = "#overview";
                window.location.reload();
              }}
              className="px-4 py-2 rounded-control bg-[#172235] hover:bg-[#232f48] text-slate-200 text-xs font-mono border border-[#243149] transition-colors"
            >
              Reset to Cockpit
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

