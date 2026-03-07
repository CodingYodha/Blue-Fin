import { useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { X } from "lucide-react";

function getNodeColor(type, riskLevel) {
  if (riskLevel === "HIGH") return "#ef4444";
  if (type === "person") return "#3b82f6";
  if (type === "company") return "#8b5cf6";
  if (type === "loan") return "#eab308";
  return "#7a7a85";
}

function LegendDot({ color, label, dashed }) {
  return (
    <div className="flex items-center gap-sm">
      {dashed ? (
        <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke={color} strokeWidth="2" strokeDasharray="4 3" /></svg>
      ) : (
        <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: color, flexShrink: 0 }} />
      )}
      <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>{label}</span>
    </div>
  );
}

export default function EntityGraphTab({ nodes, edges }) {
  const [selectedNode, setSelectedNode] = useState(null);
  const hasProbableMatch = (edges || []).some((e) => e.is_probable_match);
  const hasHighRisk = (nodes || []).some((n) => n.risk_level === "HIGH");
  const historicalNodes = (nodes || []).filter((n) => n.historical_match != null && n.historical_match !== undefined && n.historical_match !== false);

  if (!nodes || nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ padding: "80px 24px", gap: "12px" }}>
        <p style={{ fontSize: "15px", fontWeight: 500 }}>No entity relationships detected in uploaded documents.</p>
        <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>Entity graph is built from promoter names, related companies, and loan cross-references extracted via NER.</p>
      </div>
    );
  }

  const graphData = {
    nodes: nodes.map((n) => ({ id: n.id, name: n.name, type: n.type, risk_level: n.risk_level, historical_match: n.historical_match, color: getNodeColor(n.type, n.risk_level) })),
    links: edges.map((e) => ({ source: e.source, target: e.target, relationship: e.relationship, amount_crore: e.amount_crore, is_probable_match: e.is_probable_match, color: e.is_probable_match ? "#eab308" : "rgba(255,255,255,0.08)" })),
  };

  const handleNodeClick = useCallback((node) => {
    setSelectedNode((prev) => (prev && prev.id === node.id ? null : node));
  }, []);

  function riskBadge(level) {
    if (level === "HIGH") return "badge-danger";
    if (level === "MEDIUM") return "badge-warning";
    return "badge-success";
  }

  return (
    <div className="flex flex-col gap-md">
      {/* Alert banners */}
      {hasProbableMatch && (
        <div className="card" style={{ background: "var(--warning-subtle)", borderColor: "rgba(234,179,8,0.3)" }}>
          <p style={{ color: "var(--warning)", fontSize: "13px" }}>⚠ Fuzzy-matched entities detected. Manual verification recommended.</p>
        </div>
      )}
      {hasHighRisk && (
        <div className="card" style={{ background: "var(--danger-subtle)", borderColor: "rgba(239,68,68,0.3)" }}>
          <p style={{ color: "var(--danger)", fontSize: "13px" }}>🚩 Related-party anomaly detected. Possible shell company or fund siphoning risk.</p>
        </div>
      )}
      {historicalNodes.map((node) => (
        <div key={node.id} className="card" style={{ background: "var(--danger-subtle)", borderColor: "var(--danger)" }}>
          <p style={{ color: "var(--danger)", fontSize: "13px", fontWeight: 700, marginBottom: "4px" }}>⚠ HISTORICAL MATCH DETECTED</p>
          <p style={{ color: "var(--danger)", fontSize: "12px" }}>Director DIN {node.id} appeared in a previously rejected application. Escalate.</p>
        </div>
      ))}

      {/* Graph + sidebar */}
      <div className="flex gap-md">
        <div className="card" style={{ flex: 1, overflow: "hidden", padding: 0 }}>
          <ForceGraph2D
            graphData={graphData}
            nodeLabel="name"
            nodeRelSize={6}
            nodeVal={(n) => (n.risk_level === "HIGH" ? 12 : 6)}
            nodeColor={(n) => n.color}
            linkColor={(link) => link.color}
            linkWidth={(link) => (link.is_probable_match ? 1 : 2)}
            linkLineDash={(link) => (link.is_probable_match ? [3, 3] : [])}
            backgroundColor="#1a1a1f"
            width={selectedNode ? 640 : 800}
            height={500}
            onNodeClick={handleNodeClick}
          />
        </div>

        {selectedNode && (
          <div className="card shrink-0" style={{ width: "220px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div className="flex justify-between items-center">
              <span className="label">Node Detail</span>
              <button onClick={() => setSelectedNode(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)" }}>
                <X size={14} />
              </button>
            </div>
            <div className="flex flex-col gap-sm">
              <div>
                <p className="label" style={{ marginBottom: "2px" }}>Name</p>
                <p style={{ fontSize: "13px", fontWeight: 600, wordBreak: "break-word" }}>{selectedNode.name}</p>
              </div>
              <div>
                <p className="label" style={{ marginBottom: "2px" }}>Type</p>
                <p style={{ fontSize: "13px", textTransform: "capitalize" }}>{selectedNode.type}</p>
              </div>
              <div>
                <p className="label" style={{ marginBottom: "4px" }}>Risk Level</p>
                <span className={`badge ${riskBadge(selectedNode.risk_level)}`}>{selectedNode.risk_level}</span>
              </div>
              {selectedNode.historical_match && (
                <div>
                  <p className="label" style={{ marginBottom: "2px" }}>Historical Match</p>
                  <p style={{ color: "var(--danger)", fontSize: "12px" }}>Yes</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="card">
        <span className="label" style={{ display: "block", marginBottom: "12px" }}>Legend</span>
        <div className="flex flex-wrap gap-lg">
          <LegendDot color="#3b82f6" label="Person (Promoter / Director)" />
          <LegendDot color="#8b5cf6" label="Company" />
          <LegendDot color="#eab308" label="Loan / Facility" />
          <LegendDot color="#ef4444" label="HIGH RISK entity" />
          <LegendDot color="#eab308" dashed label="Probable Match (fuzzy)" />
        </div>
      </div>
    </div>
  );
}
