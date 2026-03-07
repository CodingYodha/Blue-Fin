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
        <div
          className="grid-bg page flex flex-col items-center justify-center"
          style={{ padding: "32px", textAlign: "center", gap: "20px" }}
        >
          <AlertTriangle size={48} style={{ color: "var(--danger)" }} strokeWidth={1.5} />
          <h1 style={{ fontSize: "20px", fontWeight: 600 }}>Something went wrong</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "14px", maxWidth: "400px" }}>
            {this.state.errorMessage}
          </p>
          <div className="flex gap-md">
            <button className="btn btn-secondary btn-sm" onClick={() => window.history.back()}>
              ← Go Back
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => this.setState({ hasError: false, errorMessage: "" })}>
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
