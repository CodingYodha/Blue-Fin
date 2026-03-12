import { useState, useCallback, useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { X } from "lucide-react";

const configuredBaseUrl = import.meta.env.VITE_API_URL?.trim();
const BASE_URL = configuredBaseUrl || "";

function getNodeColor(type, riskLevel) {
  if (riskLevel === "HIGH") return "#ef4444";
  if (type === "person") return "#3b82f6";
  if (type === "company") return "#8b5cf6";
  if (type === "loan") return "#eab308";
  return "#7a7a85";
}

function getNodeIcon(type) {
  if (type === "person") return "👤";
  if (type === "company") return "🏢";
  if (type === "loan") return "💰";
  return "●";
}

function LegendDot({ color, label, dashed }) {
  return (
    <div className="flex items-center gap-sm">
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
          style={{
            width: "12px",
            height: "12px",
            borderRadius: "50%",
            background: color,
            flexShrink: 0,
          }}
        />
      )}
      <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
        {label}
      </span>
    </div>
  );
}

export default function EntityGraphTab({
  nodes: propNodes,
  edges: propEdges,
  jobId,
}) {
  const [fetchedNodes, setFetchedNodes] = useState(null);
  const [fetchedEdges, setFetchedEdges] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoverNode, setHoverNode] = useState(null);
  const graphRef = useRef();

  const hasPropsData = propNodes && propNodes.length > 0;
  const nodes = hasPropsData ? propNodes : fetchedNodes;
  const edges = hasPropsData ? propEdges : fetchedEdges;

  useEffect(() => {
    if (hasPropsData || !jobId) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${BASE_URL}/api/analysis/${encodeURIComponent(jobId)}/entity-graph`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        if (data.nodes && data.nodes.length > 0) {
          setFetchedNodes(data.nodes);
          setFetchedEdges(data.edges || []);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasPropsData, jobId]);

  const hasProbableMatch = (edges || []).some((e) => e.is_probable_match);
  const hasHighRisk = (nodes || []).some((n) => n.risk_level === "HIGH");
  const historicalNodes = (nodes || []).filter(
    (n) =>
      n.historical_match != null &&
      n.historical_match !== undefined &&
      n.historical_match !== false,
  );

  if (loading) {
    return (
      <div
        className="flex flex-col items-center justify-center"
        style={{ padding: "80px 24px", gap: "12px" }}
      >
        <p style={{ fontSize: "15px", fontWeight: 500 }}>
          Loading entity graph…
        </p>
      </div>
    );
  }

  if (!nodes || nodes.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center"
        style={{ padding: "80px 24px", gap: "12px" }}
      >
        <p style={{ fontSize: "15px", fontWeight: 500 }}>
          No entity relationships detected in uploaded documents.
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>
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
      color: e.is_probable_match ? "#eab308" : "rgba(255,255,255,0.08)",
    })),
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
        <div
          className="card"
          style={{
            background: "var(--warning-subtle)",
            borderColor: "rgba(234,179,8,0.3)",
          }}
        >
          <p style={{ color: "var(--warning)", fontSize: "13px" }}>
            ⚠ Fuzzy-matched entities detected. Manual verification recommended.
          </p>
        </div>
      )}
      {hasHighRisk && (
        <div
          className="card"
          style={{
            background: "var(--danger-subtle)",
            borderColor: "rgba(239,68,68,0.3)",
          }}
        >
          <p style={{ color: "var(--danger)", fontSize: "13px" }}>
            🚩 Related-party anomaly detected. Possible shell company or fund
            siphoning risk.
          </p>
        </div>
      )}
      {historicalNodes.map((node) => (
        <div
          key={node.id}
          className="card"
          style={{
            background: "var(--danger-subtle)",
            borderColor: "var(--danger)",
          }}
        >
          <p
            style={{
              color: "var(--danger)",
              fontSize: "13px",
              fontWeight: 700,
              marginBottom: "4px",
            }}
          >
            ⚠ HISTORICAL MATCH DETECTED
          </p>
          <p style={{ color: "var(--danger)", fontSize: "12px" }}>
            Director DIN {node.id} appeared in a previously rejected
            application. Escalate.
          </p>
        </div>
      ))}

      {/* Graph + sidebar */}
      <div className="flex gap-md">
        <div
          className="card"
          style={{
            flex: 1,
            overflow: "hidden",
            padding: 0,
            background:
              "linear-gradient(135deg, #1a1a1f 0%, #1e1e28 50%, #1a1a22 100%)",
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: 0.04,
              background:
                "radial-gradient(circle at 50% 50%, #3b82f6 0%, transparent 60%)",
              pointerEvents: "none",
            }}
          />
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeRelSize={6}
            nodeVal={(n) => (n.risk_level === "HIGH" ? 12 : 6)}
            linkWidth={(link) => (link.is_probable_match ? 1.5 : 2.5)}
            linkLineDash={(link) => (link.is_probable_match ? [4, 4] : [])}
            backgroundColor="transparent"
            width={selectedNode ? 640 : 800}
            height={500}
            onNodeClick={handleNodeClick}
            onNodeHover={(node) => setHoverNode(node || null)}
            cooldownTicks={80}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            nodeCanvasObject={(node, ctx, globalScale) => {
              if (typeof node.x !== "number" || typeof node.y !== "number")
                return;

              const r = node.risk_level === "HIGH" ? 10 : 7;
              const isHover = hoverNode && hoverNode.id === node.id;
              const isSel = selectedNode && selectedNode.id === node.id;
              const color = node.color;

              // Outer glow
              ctx.beginPath();
              ctx.arc(node.x, node.y, r + (isHover ? 8 : 4), 0, 2 * Math.PI);
              const grad = ctx.createRadialGradient(
                node.x,
                node.y,
                r,
                node.x,
                node.y,
                r + (isHover ? 14 : 6),
              );
              grad.addColorStop(0, color + (isHover ? "55" : "25"));
              grad.addColorStop(1, color + "00");
              ctx.fillStyle = grad;
              ctx.fill();

              // Ring for selected
              if (isSel) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI);
                ctx.strokeStyle = "#ffffff55";
                ctx.lineWidth = 1.5;
                ctx.stroke();
              }

              // Main circle
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              const cGrad = ctx.createRadialGradient(
                node.x - r * 0.3,
                node.y - r * 0.3,
                r * 0.1,
                node.x,
                node.y,
                r,
              );
              cGrad.addColorStop(0, color + "ff");
              cGrad.addColorStop(1, color + "aa");
              ctx.fillStyle = cGrad;
              ctx.fill();
              ctx.strokeStyle = color + "88";
              ctx.lineWidth = 1;
              ctx.stroke();

              // High-risk outer ring
              if (node.risk_level === "HIGH") {
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 5, 0, 2 * Math.PI);
                ctx.strokeStyle = "rgba(239,68,68,0.25)";
                ctx.lineWidth = 1.5;
                ctx.stroke();
              }

              // Label
              const labelSize = isHover ? 12 : 10;
              ctx.font = `${isHover ? "600" : "500"} ${labelSize / globalScale}px Inter, sans-serif`;
              ctx.fillStyle = isHover ? "#ffffff" : "#b8b8bfcc";
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillText(node.name, node.x, node.y + r + 4 / globalScale);
            }}
            nodePointerAreaPaint={(node, color, ctx) => {
              const r = node.risk_level === "HIGH" ? 14 : 10;
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            linkCanvasObject={(link, ctx) => {
              const start = link.source;
              const end = link.target;
              if (
                !start ||
                !end ||
                typeof start.x !== "number" ||
                typeof start.y !== "number" ||
                typeof end.x !== "number" ||
                typeof end.y !== "number"
              )
                return;

              ctx.beginPath();
              ctx.moveTo(start.x, start.y);
              ctx.lineTo(end.x, end.y);

              if (link.is_probable_match) {
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = "rgba(234,179,8,0.5)";
                ctx.lineWidth = 1.5;
              } else {
                ctx.setLineDash([]);
                const grad = ctx.createLinearGradient(
                  start.x,
                  start.y,
                  end.x,
                  end.y,
                );
                grad.addColorStop(0, (start.color || "#3b82f6") + "55");
                grad.addColorStop(0.5, "rgba(255,255,255,0.12)");
                grad.addColorStop(1, (end.color || "#3b82f6") + "55");
                ctx.strokeStyle = grad;
                ctx.lineWidth = 2;
              }
              ctx.stroke();
              ctx.setLineDash([]);

              // Relationship label
              if (link.relationship) {
                const mx = (start.x + end.x) / 2;
                const my = (start.y + end.y) / 2;
                ctx.font = "500 3px Inter, sans-serif";
                ctx.fillStyle = "rgba(255,255,255,0.25)";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(link.relationship, mx, my - 3);
              }
            }}
          />
        </div>

        {selectedNode && (
          <div
            className="card shrink-0"
            style={{
              width: "220px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <div className="flex justify-between items-center">
              <span className="label">Node Detail</span>
              <button
                onClick={() => setSelectedNode(null)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-muted)",
                }}
              >
                <X size={14} />
              </button>
            </div>
            <div className="flex flex-col gap-sm">
              <div>
                <p className="label" style={{ marginBottom: "2px" }}>
                  Name
                </p>
                <p
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    wordBreak: "break-word",
                  }}
                >
                  {selectedNode.name}
                </p>
              </div>
              <div>
                <p className="label" style={{ marginBottom: "2px" }}>
                  Type
                </p>
                <p style={{ fontSize: "13px", textTransform: "capitalize" }}>
                  {selectedNode.type}
                </p>
              </div>
              <div>
                <p className="label" style={{ marginBottom: "4px" }}>
                  Risk Level
                </p>
                <span className={`badge ${riskBadge(selectedNode.risk_level)}`}>
                  {selectedNode.risk_level}
                </span>
              </div>
              {selectedNode.historical_match && (
                <div>
                  <p className="label" style={{ marginBottom: "2px" }}>
                    Historical Match
                  </p>
                  <p style={{ color: "var(--danger)", fontSize: "12px" }}>
                    Yes
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="card">
        <span
          className="label"
          style={{ display: "block", marginBottom: "12px" }}
        >
          Legend
        </span>
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
