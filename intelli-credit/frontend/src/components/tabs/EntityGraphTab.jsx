import { useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { X } from "lucide-react";

function getNodeColor(type, riskLevel) {
  if (riskLevel === "HIGH") return "#ef4444";
  if (type === "person") return "#00d4ff";
  if (type === "company") return "#7c3aed";
  if (type === "loan") return "#f59e0b";
  return "#64748b";
}

function LegendDot({ color, label, dashed }) {
  return (
    <div className="flex items-center gap-2">
      {dashed ? (
        <svg width="24" height="8">
          <line
            x1="0"
            y1="4"
            x2="24"
            y2="4"
            stroke={color}
            strokeWidth="2"
            strokeDasharray="4 3"
          />
        </svg>
      ) : (
        <div
          className="w-3 h-3 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
      )}
      <span className="text-muted text-xs font-mono">{label}</span>
    </div>
  );
}

export default function EntityGraphTab({ nodes, edges }) {
  const [selectedNode, setSelectedNode] = useState(null);

  const hasProbableMatch = (edges || []).some((e) => e.is_probable_match);
  const hasHighRisk = (nodes || []).some((n) => n.risk_level === "HIGH");
  const historicalNodes = (nodes || []).filter(
    (n) =>
      n.historical_match != null &&
      n.historical_match !== undefined &&
      n.historical_match !== false,
  );

  if (!nodes || nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-textprimary font-mono text-base">
          No entity relationships detected in uploaded documents.
        </p>
        <p className="text-muted text-sm">
          Entity graph is built from promoter names, related companies, and loan
          cross-references extracted via NER.
        </p>
      </div>
    );
  }

  const graphData = {
    nodes: nodes.map((n) => ({
      id: n.id,
      name: n.name,
      type: n.type,
      risk_level: n.risk_level,
      historical_match: n.historical_match,
      color: getNodeColor(n.type, n.risk_level),
    })),
    links: edges.map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.relationship,
      amount_crore: e.amount_crore,
      is_probable_match: e.is_probable_match,
      color: e.is_probable_match ? "#f59e0b" : "#1e2d45",
    })),
  };

  const handleNodeClick = useCallback((node) => {
    setSelectedNode((prev) => (prev && prev.id === node.id ? null : node));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      {/* Alert banners */}
      {hasProbableMatch && (
        <div className="bg-warn/10 border border-warn/50 rounded-xl px-5 py-3">
          <p className="text-warn font-mono text-sm">
            ⚠ Fuzzy-matched entities detected. These connections were identified
            by approximate name matching (thefuzz score 70-85). Manual
            verification recommended.
          </p>
        </div>
      )}
      {hasHighRisk && (
        <div className="bg-danger/10 border border-danger/50 rounded-xl px-5 py-3">
          <p className="text-danger font-mono text-sm">
            🚩 Related-party anomaly detected. Possible shell company or fund
            siphoning risk.
          </p>
        </div>
      )}
      {historicalNodes.map((node) => (
        <div
          key={node.id}
          className="bg-danger/10 border border-danger rounded-xl px-5 py-3"
        >
          <p className="text-danger font-mono text-sm font-semibold mb-1">
            ⚠ HISTORICAL MATCH DETECTED
          </p>
          <p className="text-danger font-mono text-xs">
            Director DIN {node.id} appeared in a previously rejected
            application. This may indicate a known fraud network. Escalate to
            senior credit committee.
          </p>
        </div>
      ))}

      {/* Graph + sidebar */}
      <div className="flex gap-4">
        <div className="flex-1 bg-surface border border-border rounded-xl overflow-hidden relative">
          <ForceGraph2D
            graphData={graphData}
            nodeLabel="name"
            nodeRelSize={6}
            nodeVal={(n) => (n.risk_level === "HIGH" ? 12 : 6)}
            nodeColor={(n) => n.color}
            linkColor={(link) => link.color}
            linkWidth={(link) => (link.is_probable_match ? 1 : 2)}
            linkLineDash={(link) => (link.is_probable_match ? [3, 3] : [])}
            backgroundColor="#05080f"
            width={selectedNode ? 640 : 800}
            height={500}
            onNodeClick={handleNodeClick}
          />
        </div>

        {/* Node detail sidebar */}
        {selectedNode && (
          <div className="w-56 bg-surface border border-border rounded-xl p-4 flex flex-col gap-3 flex-shrink-0">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xs text-muted uppercase tracking-widest">
                Node Detail
              </p>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-muted hover:text-textprimary"
              >
                <X size={14} />
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <div>
                <p className="text-muted text-xs font-mono">Name</p>
                <p className="text-textprimary text-sm font-mono font-semibold break-words">
                  {selectedNode.name}
                </p>
              </div>
              <div>
                <p className="text-muted text-xs font-mono">Type</p>
                <p className="text-textprimary text-sm font-mono capitalize">
                  {selectedNode.type}
                </p>
              </div>
              <div>
                <p className="text-muted text-xs font-mono">Risk Level</p>
                <span
                  className={`font-mono text-xs px-2 py-0.5 rounded-full border ${
                    selectedNode.risk_level === "HIGH"
                      ? "bg-danger/20 text-danger border-danger/50"
                      : selectedNode.risk_level === "MEDIUM"
                        ? "bg-warn/20 text-warn border-warn/50"
                        : "bg-accent3/20 text-accent3 border-accent3/50"
                  }`}
                >
                  {selectedNode.risk_level}
                </span>
              </div>
              {selectedNode.historical_match && (
                <div>
                  <p className="text-muted text-xs font-mono">
                    Historical Match
                  </p>
                  <p className="text-danger text-xs font-mono">Yes</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <p className="font-mono text-muted text-xs tracking-widest uppercase mb-3">
          LEGEND
        </p>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <LegendDot color="#00d4ff" label="Person (Promoter / Director)" />
          <LegendDot color="#7c3aed" label="Company" />
          <LegendDot color="#f59e0b" label="Loan / Facility" />
          <LegendDot color="#ef4444" label="HIGH RISK entity" />
          <LegendDot
            color="#f59e0b"
            dashed
            label="Probable Match (fuzzy, 70-85% confidence)"
          />
        </div>
      </div>
    </div>
  );
}
