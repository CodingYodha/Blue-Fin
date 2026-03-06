import React from "react";
import { AlertTriangle } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, errorMessage: error.message };
  }

  componentDidCatch(error, info) {
    console.error(error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-bg flex flex-col items-center justify-center gap-5 p-8 text-center">
          <AlertTriangle size={48} className="text-danger" strokeWidth={1.5} />
          <h1 className="text-xl font-bold text-textprimary">
            Something went wrong
          </h1>
          <p className="text-muted text-sm max-w-md">
            {this.state.errorMessage}
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => window.history.back()}
              className="rounded-lg border border-border px-4 py-2 text-sm text-textprimary hover:bg-surface2 transition-colors"
            >
              ← Go Back
            </button>
            <button
              onClick={() =>
                this.setState({ hasError: false, errorMessage: "" })
              }
              className="rounded-lg bg-accent/10 border border-accent/30 px-4 py-2 text-sm text-accent hover:bg-accent/20 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
