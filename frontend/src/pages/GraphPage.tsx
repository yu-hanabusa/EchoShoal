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

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <p className="text-sm text-text-tertiary">Loading graph...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <p className="text-sm text-negative">Failed to load graph. Is Neo4j running?</p>
      </div>
    );
  }

  if (!data?.elements?.length) {
    return (
      <div className="min-h-screen bg-surface-1">
        <main className="max-w-5xl mx-auto px-4 py-8">
          <h1 className="text-lg font-semibold text-text-primary mb-4">Knowledge Graph</h1>
          <p className="text-sm text-text-tertiary">
            No graph data available. Upload documents or run data collection first.
          </p>
        </main>
      </div>
    );
  }

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

  // Simple layout: group by type in rows
  const typeGroups: Record<string, GraphNode[]> = {};
  for (const node of nodes) {
    if (!typeGroups[node.type]) typeGroups[node.type] = [];
    typeGroups[node.type].push(node);
  }

  const typeOrder = ["Industry", "SkillCategory", "Skill", "Role", "Policy", "Document"];
  const width = 1100;
  let currentY = 60;

  for (const type of typeOrder) {
    const group = typeGroups[type];
    if (!group) continue;
    const spacing = Math.min(120, (width - 100) / Math.max(group.length, 1));
    const startX = (width - spacing * (group.length - 1)) / 2;
    group.forEach((node, i) => {
      node.x = startX + i * spacing;
      node.y = currentY + (Math.random() * 20 - 10);
    });
    currentY += 110;
  }

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
  const svgHeight = Math.max(currentY + 40, 400);

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-lg font-semibold text-text-primary mb-4">Knowledge Graph</h1>

        {/* Legend */}
        <div className="flex gap-4 mb-4 flex-wrap">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5 text-xs text-text-secondary">
              <span
                className="inline-block w-3 h-3 rounded-full"
                style={{ backgroundColor: color }}
              />
              {type}
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-border overflow-hidden bg-surface-0">
          <svg width="100%" viewBox={`0 0 ${width} ${svgHeight}`}>
            {/* Edges */}
            {edges.map((edge, i) => {
              const s = nodeMap.get(edge.source);
              const t = nodeMap.get(edge.target);
              if (!s || !t) return null;
              return (
                <line
                  key={`e-${i}`}
                  x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                  stroke="#d1d5db" strokeWidth={1} opacity={0.6}
                />
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => {
              const color = NODE_COLORS[node.type] || "#9ca3af";
              const size = NODE_SIZES[node.type] || 14;
              return (
                <g key={node.id}>
                  <circle cx={node.x} cy={node.y} r={size / 2} fill={color} opacity={0.85} />
                  <text
                    x={node.x} y={node.y + size / 2 + 12}
                    textAnchor="middle" fontSize={9} fill="#4b5563"
                  >
                    {node.label.length > 12 ? node.label.slice(0, 12) + "..." : node.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <p className="text-xs text-text-tertiary mt-2">
          {nodes.length} nodes, {edges.length} edges
        </p>
      </main>
    </div>
  );
}
