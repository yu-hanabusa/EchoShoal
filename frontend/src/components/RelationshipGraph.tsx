import { useState, useMemo } from "react";
import type { RoundResult, AgentSummary } from "../api/types";

const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
  "#14b8a6", "#e879f9", "#78716c", "#fb923c", "#a3e635",
];

const RELATION_COLORS: Record<string, string> = {
  competitor: "#ef4444",
  partner: "#10b981",
  investor: "#f59e0b",
  regulator: "#6366f1",
  acquirer: "#ec4899",
  user: "#3b82f6",
  advocate: "#34d399",
  critic: "#f97316",
  former_user: "#9ca3af",
  interaction: "#d1d5db",
};

const RELATION_LABELS: Record<string, string> = {
  competitor: "競合",
  partner: "提携",
  investor: "投資",
  regulator: "規制",
  acquirer: "買収",
  user: "利用",
  advocate: "推薦",
  critic: "批判",
  former_user: "離脱",
  interaction: "影響",
};

interface Props {
  rounds: RoundResult[];
  agents: AgentSummary[];
}

interface Edge {
  from: string;
  to: string;
  type: string;
  round: number;
  description: string;
}

export default function RelationshipGraph({ rounds, agents }: Props) {
  const totalRounds = rounds.length;
  const [selectedRound, setSelectedRound] = useState(totalRounds);

  // エージェント名→色マッピング
  const agentColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    agents.forEach((a, i) => { map[a.name] = AGENT_COLORS[i % AGENT_COLORS.length]; });
    return map;
  }, [agents]);

  // 全ラウンドからreacting_to関係を収集
  const allEdges = useMemo(() => {
    const edges: Edge[] = [];
    for (const r of rounds) {
      for (const a of r.actions_taken) {
        if (a.reacting_to) {
          // アクションタイプから関係を推定
          const typeMap: Record<string, string> = {
            build_competitor: "competitor", launch_competing_product: "competitor",
            launch_competing_feature: "competitor", price_undercut: "competitor",
            partner: "partner", partner_integrate: "partner",
            invest_seed: "investor", invest_series: "investor", fund_competitor: "investor",
            regulate: "regulator", investigate: "regulator",
            acquire_service: "acquirer", acquire_startup: "acquirer",
            adopt_new_service: "user", adopt_service: "user", adopt_tool: "user",
            recommend: "advocate", complain: "critic", churn: "former_user",
          };
          edges.push({
            from: a.agent,
            to: a.reacting_to,
            type: typeMap[a.type] || "interaction",
            round: r.round_number,
            description: `${a.agent} → ${a.type} → ${a.reacting_to}`,
          });
        }
      }
    }
    return edges;
  }, [rounds]);

  // 選択ラウンドまでのエッジをフィルタ（最新の関係のみ）
  const visibleEdges = useMemo(() => {
    const filtered = allEdges.filter((e) => e.round <= selectedRound);
    // from-to ペアごとに最新の関係のみ残す
    const latest = new Map<string, Edge>();
    for (const e of filtered) {
      const key = `${e.from}→${e.to}`;
      const existing = latest.get(key);
      if (!existing || e.round > existing.round) {
        latest.set(key, e);
      }
    }
    return Array.from(latest.values());
  }, [allEdges, selectedRound]);

  // アクティブなエージェント（エッジに関与するもの）
  const activeAgentNames = useMemo(() => {
    const names = new Set<string>();
    for (const e of visibleEdges) {
      names.add(e.from);
      names.add(e.to);
    }
    // エッジがなくてもエージェントは全員表示
    for (const a of agents) names.add(a.name);
    return Array.from(names);
  }, [visibleEdges, agents]);

  // 円形レイアウト
  const width = 700;
  const height = 500;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(cx, cy) - 60;

  const nodePositions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    activeAgentNames.forEach((name, i) => {
      const angle = (2 * Math.PI * i) / activeAgentNames.length - Math.PI / 2;
      pos[name] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      };
    });
    return pos;
  }, [activeAgentNames, cx, cy, radius]);

  // 選択ラウンドのアクション
  const roundActions = useMemo(() => {
    const r = rounds.find((r) => r.round_number === selectedRound);
    return r?.actions_taken || [];
  }, [rounds, selectedRound]);

  const roundNarrative = rounds.find((r) => r.round_number === selectedRound)?.summary || "";

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-text-primary">ステークホルダー関係図</h3>
        <span className="text-xs text-text-tertiary">
          {selectedRound}ヶ月目 / {totalRounds}ヶ月
        </span>
      </div>

      {/* タイムスライダー */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-xs text-text-tertiary shrink-0">1</span>
        <input
          type="range"
          min={1}
          max={totalRounds}
          value={selectedRound}
          onChange={(e) => setSelectedRound(Number(e.target.value))}
          className="flex-1"
        />
        <span className="text-xs text-text-tertiary shrink-0">{totalRounds}</span>
      </div>

      {/* グラフ */}
      <div className="rounded-lg border border-border overflow-hidden bg-surface-1">
        <svg width="100%" viewBox={`0 0 ${width} ${height}`}>
          {/* エッジ */}
          {visibleEdges.map((e, i) => {
            const from = nodePositions[e.from];
            const to = nodePositions[e.to];
            if (!from || !to) return null;
            const color = RELATION_COLORS[e.type] || "#d1d5db";
            // 矢印の方向を計算
            const dx = to.x - from.x;
            const dy = to.y - from.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const nx = dx / dist;
            const ny = dy / dist;
            // ノード半径分手前で止める
            const r = 24;
            const x1 = from.x + nx * r;
            const y1 = from.y + ny * r;
            const x2 = to.x - nx * r;
            const y2 = to.y - ny * r;
            // 矢印ヘッド
            const headLen = 8;
            const angle = Math.atan2(y2 - y1, x2 - x1);
            const ax1 = x2 - headLen * Math.cos(angle - 0.4);
            const ay1 = y2 - headLen * Math.sin(angle - 0.4);
            const ax2 = x2 - headLen * Math.cos(angle + 0.4);
            const ay2 = y2 - headLen * Math.sin(angle + 0.4);

            return (
              <g key={i}>
                <line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={color} strokeWidth={2} opacity={0.7} />
                <polygon points={`${x2},${y2} ${ax1},${ay1} ${ax2},${ay2}`}
                  fill={color} opacity={0.7} />
                {/* 関係ラベル */}
                <text
                  x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6}
                  textAnchor="middle" fontSize={9} fill={color} fontWeight={600}
                >
                  {RELATION_LABELS[e.type] || e.type}
                </text>
              </g>
            );
          })}

          {/* ノード */}
          {activeAgentNames.map((name) => {
            const pos = nodePositions[name];
            if (!pos) return null;
            const agent = agents.find((a) => a.name === name);
            const isArchetype = agent?.mode === "archetype";
            const rc = agent?.represents_count || 1;
            const nodeRadius = isArchetype ? 22 + Math.min(rc / 10, 8) : 20;
            const color = agentColorMap[name] || "#94a3b8";
            const hasAction = roundActions.some((a) => a.agent === name);

            return (
              <g key={name}>
                <circle
                  cx={pos.x} cy={pos.y} r={nodeRadius}
                  fill={color} opacity={hasAction ? 0.9 : 0.4}
                  stroke={hasAction ? "#1e293b" : "none"}
                  strokeWidth={hasAction ? 2 : 0}
                />
                {isArchetype && (
                  <circle cx={pos.x} cy={pos.y} r={nodeRadius}
                    fill="none" stroke={color} strokeWidth={2} strokeDasharray="3 2" opacity={0.6} />
                )}
                <text
                  x={pos.x} y={pos.y + nodeRadius + 14}
                  textAnchor="middle" fontSize={10} fill="#475569" fontWeight={500}
                >
                  {name.length > 12 ? name.slice(0, 12) + ".." : name}
                </text>
                {rc > 1 && (
                  <text
                    x={pos.x} y={pos.y + 4}
                    textAnchor="middle" fontSize={9} fill="white" fontWeight={700}
                  >
                    ×{rc}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* 凡例 */}
      <div className="flex flex-wrap gap-3 mt-3">
        {Object.entries(RELATION_LABELS).filter(([k]) => visibleEdges.some((e) => e.type === k)).map(([type, label]) => (
          <div key={type} className="flex items-center gap-1 text-xs text-text-secondary">
            <span className="inline-block w-3 h-0.5" style={{ backgroundColor: RELATION_COLORS[type] }} />
            {label}
          </div>
        ))}
      </div>

      {/* ラウンドのナラティブ */}
      {roundNarrative && (
        <p className="text-sm text-text-secondary mt-3 italic border-l-2 border-interactive pl-3">
          {roundNarrative}
        </p>
      )}
    </div>
  );
}
