import { useQuery } from "@tanstack/react-query";
import { getGraphVisualization } from "../api/client";

const NODE_COLORS: Record<string, string> = {
  Industry: "#3b82f6",
  SkillCategory: "#10b981",
  Skill: "#6ee7b7",
  Role: "#f97316",
  Policy: "#ef4444",
  Document: "#8b5cf6",
};

const NODE_SIZES: Record<string, number> = {
  Industry: 24,
  SkillCategory: 20,
  Skill: 14,
  Role: 16,
  Policy: 18,
  Document: 16,
};

interface GraphNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export default function GraphPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["graph-visualization"],
    queryFn: getGraphVisualization,
  });

  if (isLoading) return <div style={{ padding: "2rem", textAlign: "center" }}>Loading graph...</div>;
  if (error) return <div style={{ padding: "2rem", textAlign: "center", color: "#ef4444" }}>Failed to load graph. Is Neo4j running?</div>;
  if (!data?.elements?.length) return <div style={{ padding: "2rem", textAlign: "center" }}>No graph data available.</div>;

  // Separate nodes and edges
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  for (const el of data.elements) {
    if (el.data.source && el.data.target) {
      edges.push({ source: el.data.source, target: el.data.target, label: el.data.label || "" });
    } else if (el.data.id) {
      nodes.push({ id: el.data.id, label: el.data.label || el.data.id, type: el.data.type || "Unknown", x: 0, y: 0 });
    }
  }

  // Simple force-directed layout approximation (group by type)
  const typeGroups: Record<string, GraphNode[]> = {};
  for (const node of nodes) {
    if (!typeGroups[node.type]) typeGroups[node.type] = [];
    typeGroups[node.type].push(node);
  }

  const typeOrder = ["Industry", "SkillCategory", "Skill", "Role", "Policy", "Document"];
  const width = 1100;
  const height = 700;
  let currentY = 60;

  for (const type of typeOrder) {
    const group = typeGroups[type];
    if (!group) continue;
    const spacing = Math.min(120, (width - 100) / Math.max(group.length, 1));
    const startX = (width - spacing * (group.length - 1)) / 2;
    group.forEach((node, i) => {
      node.x = startX + i * spacing;
      node.y = currentY + (Math.random() * 20 - 10); // slight jitter
    });
    currentY += 110;
  }

  // Handle any types not in typeOrder
  for (const [type, group] of Object.entries(typeGroups)) {
    if (typeOrder.includes(type)) continue;
    const spacing = Math.min(120, (width - 100) / Math.max(group.length, 1));
    const startX = (width - spacing * (group.length - 1)) / 2;
    group.forEach((node, i) => {
      node.x = startX + i * spacing;
      node.y = currentY;
    });
    currentY += 110;
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem" }}>
      <h1 style={{ marginBottom: "1rem" }}>Knowledge Graph</h1>

      {/* Legend */}
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.8rem" }}>
            <span style={{ width: "12px", height: "12px", borderRadius: "50%", backgroundColor: color, display: "inline-block" }} />
            {type}
          </div>
        ))}
      </div>

      <div style={{ border: "1px solid #e5e7eb", borderRadius: "8px", overflow: "hidden", backgroundColor: "#fafafa" }}>
        <svg width="100%" viewBox={`0 0 ${width} ${Math.max(currentY + 40, height)}`}>
          {/* Edges */}
          {edges.map((edge, i) => {
            const s = nodeMap.get(edge.source);
            const t = nodeMap.get(edge.target);
            if (!s || !t) return null;
            return (
              <line
                key={`e-${i}`}
                x1={s.x}
                y1={s.y}
                x2={t.x}
                y2={t.y}
                stroke="#d1d5db"
                strokeWidth={1}
                opacity={0.6}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const color = NODE_COLORS[node.type] || "#9ca3af";
            const size = NODE_SIZES[node.type] || 14;
            return (
              <g key={node.id}>
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={size / 2}
                  fill={color}
                  opacity={0.85}
                />
                <text
                  x={node.x}
                  y={node.y + size / 2 + 12}
                  textAnchor="middle"
                  fontSize={9}
                  fill="#4b5563"
                >
                  {node.label.length > 12 ? node.label.slice(0, 12) + "..." : node.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <p style={{ color: "#9ca3af", fontSize: "0.8rem", marginTop: "0.5rem" }}>
        {nodes.length} nodes, {edges.length} edges
      </p>
    </div>
  );
}
