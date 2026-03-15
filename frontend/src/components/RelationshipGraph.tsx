import { useState, useMemo } from "react";
import type { RoundResult, AgentSummary } from "../api/types";

/** アクションタイプを日本語に変換 */
const ACTION_LABELS: Record<string, string> = {
  adopt_service: "サービス採用", build_competitor: "競合開発", invest: "投資",
  regulate: "規制", partner: "提携", observe: "様子見", ignore: "無視",
  adopt_new_service: "新サービス採用", stay_with_current: "現状維持",
  trial: "試用", churn: "解約", recommend: "推薦", complain: "不満表明",
  compare_alternatives: "比較検討", create_post: "投稿", comment: "コメント",
  like: "いいね", follow: "フォロー", repost: "リポスト", sign_up: "登録",
  refresh: "更新確認", login: "ログイン",
  set_regulation: "規制設定", issue_subsidy: "補助金発行",
  announce_policy: "政策発表", provide_platform: "基盤提供",
  launch_competing_feature: "競合機能発表", acquire_startup: "スタートアップ買収",
  form_standards_group: "標準化団体設立", host_event: "イベント開催",
  publish_research: "調査公開", fund_startup: "スタートアップ出資",
  exit_investment: "投資撤退",
};

/** 投稿内容をクリーンアップ */
function cleanDescription(raw: string): string {
  let s = raw;
  s = s.replace(/\(Impact:\s*[^)]*\)/gi, "");
  s = s.replace(/\{["\u0027](?:posts|user_id|post_id|name|user_name|bio|content)["\u0027]\s*:[\s\S]{0,200}/g, "");
  s = s.replace(/^(sign_up|refresh|login|logout|create_post|like|dislike|follow|unfollow)\s*$/gm, "");
  s = s.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
  s = s.replace(/^\s*\{[^}]*$|^[^{]*\}\s*$/gm, "");
  return s.trim();
}

const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
  "#14b8a6", "#e879f9", "#78716c", "#fb923c", "#a3e635",
];

const RELATION_COLORS: Record<string, string> = {
  competitor: "#ef4444", partner: "#10b981", investor: "#f59e0b",
  regulator: "#6366f1", acquirer: "#ec4899", user: "#3b82f6",
  advocate: "#34d399", critic: "#f97316", former_user: "#9ca3af",
  interaction: "#d1d5db",
  // OASIS interaction types
  interest: "#60a5fa", discussion: "#a78bfa", amplification: "#fbbf24",
  support: "#34d399", opposition: "#ef4444", reference: "#06b6d4",
};

const RELATION_LABELS: Record<string, string> = {
  competitor: "競合", partner: "提携", investor: "投資",
  regulator: "規制", acquirer: "買収", user: "利用",
  advocate: "推薦", critic: "批判", former_user: "離脱",
  interaction: "影響",
  // OASIS interaction types
  interest: "関心", discussion: "議論", amplification: "拡散",
  support: "支持", opposition: "反対", reference: "引用",
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
  weight: number;
}

export default function RelationshipGraph({ rounds, agents }: Props) {
  const totalRounds = rounds.length;
  const [selectedRound, setSelectedRound] = useState(totalRounds);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const agentColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    agents.forEach((a, i) => { map[a.name] = AGENT_COLORS[i % AGENT_COLORS.length]; });
    return map;
  }, [agents]);

  // 全エッジを収集（weight = 同一方向の累積インタラクション数）
  const allEdges = useMemo(() => {
    const edgeMap = new Map<string, Edge>();
    const typeMap: Record<string, string> = {
      build_competitor: "competitor", launch_competing_product: "competitor",
      launch_competing_feature: "competitor", price_undercut: "competitor",
      partner: "partner", partner_integrate: "partner",
      invest_seed: "investor", invest_series: "investor", fund_competitor: "investor",
      regulate: "regulator", investigate: "regulator",
      acquire_service: "acquirer", acquire_startup: "acquirer",
      adopt_new_service: "user", adopt_service: "user", adopt_tool: "user",
      recommend: "advocate", complain: "critic", churn: "former_user",
      // OASIS action mappings
      post_opinion: "discussion", comment: "discussion",
      endorse: "support", critique: "opposition", amplify: "amplification",
      quote_opinion: "reference", follow_stakeholder: "interest",
      market_research: "interest",
    };
    for (const r of rounds) {
      for (const a of r.actions_taken) {
        if (a.reacting_to) {
          const relType = typeMap[a.type] || "interaction";
          const key = `${a.agent}→${a.reacting_to}→${relType}`;
          const existing = edgeMap.get(key);
          if (existing) {
            existing.weight += 1;
            existing.round = Math.max(existing.round, r.round_number);
          } else {
            edgeMap.set(key, {
              from: a.agent, to: a.reacting_to,
              type: relType,
              round: r.round_number,
              weight: 1,
            });
          }
        }
      }
    }
    return Array.from(edgeMap.values());
  }, [rounds]);

  // 選択ラウンドまでに「登場した」エージェント（行動したことがある）
  const appearedAgents = useMemo(() => {
    const appeared = new Set<string>();
    for (const r of rounds) {
      if (r.round_number > selectedRound) break;
      for (const a of r.actions_taken) {
        appeared.add(a.agent);
        if (a.reacting_to) appeared.add(a.reacting_to);
      }
    }
    return Array.from(appeared);
  }, [rounds, selectedRound]);

  // 選択ラウンドまでのエッジ（最新のみ）
  const visibleEdges = useMemo(() => {
    const filtered = allEdges.filter((e) => e.round <= selectedRound);
    const latest = new Map<string, Edge>();
    for (const e of filtered) {
      latest.set(`${e.from}→${e.to}`, e);
    }
    return Array.from(latest.values());
  }, [allEdges, selectedRound]);

  // 選択ラウンドの行動
  const roundActions = useMemo(() => {
    const r = rounds.find((r) => r.round_number === selectedRound);
    return r?.actions_taken || [];
  }, [rounds, selectedRound]);

  const roundNarrative = rounds.find((r) => r.round_number === selectedRound)?.summary || "";

  // レイアウト
  const width = 700;
  const height = 500;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(cx, cy) - 70;

  const nodePositions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    appearedAgents.forEach((name, i) => {
      const angle = (2 * Math.PI * i) / Math.max(appearedAgents.length, 1) - Math.PI / 2;
      pos[name] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      };
    });
    return pos;
  }, [appearedAgents, cx, cy, radius]);

  // 選択エージェントの情報
  const selectedAgentInfo = agents.find((a) => a.name === selectedAgent);
  const selectedAgentActions = roundActions.filter((a) => a.agent === selectedAgent);

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-text-primary">ステークホルダー関係図</h3>
        <span className="text-xs text-text-tertiary">
          {selectedRound}ヶ月目 / {totalRounds}ヶ月 — {appearedAgents.length}ステークホルダー登場
        </span>
      </div>

      {/* タイムスライダー */}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={() => setSelectedRound(Math.max(1, selectedRound - 1))}
          className="text-xs px-2 py-1 rounded bg-surface-2 text-text-secondary hover:bg-border"
        >
          ◀
        </button>
        <input
          type="range"
          min={1}
          max={totalRounds}
          value={selectedRound}
          onChange={(e) => { setSelectedRound(Number(e.target.value)); setSelectedAgent(null); }}
          className="flex-1"
        />
        <button
          onClick={() => setSelectedRound(Math.min(totalRounds, selectedRound + 1))}
          className="text-xs px-2 py-1 rounded bg-surface-2 text-text-secondary hover:bg-border"
        >
          ▶
        </button>
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
            const dx = to.x - from.x;
            const dy = to.y - from.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist === 0) return null;
            const nx = dx / dist;
            const ny = dy / dist;
            const r = 24;
            const x1 = from.x + nx * r;
            const y1 = from.y + ny * r;
            const x2 = to.x - nx * r;
            const y2 = to.y - ny * r;
            const headLen = 8;
            const angle = Math.atan2(y2 - y1, x2 - x1);
            const ax1 = x2 - headLen * Math.cos(angle - 0.4);
            const ay1 = y2 - headLen * Math.sin(angle - 0.4);
            const ax2 = x2 - headLen * Math.cos(angle + 0.4);
            const ay2 = y2 - headLen * Math.sin(angle + 0.4);
            const isHighlighted = selectedAgent === e.from || selectedAgent === e.to;

            return (
              <g key={i} opacity={selectedAgent ? (isHighlighted ? 1 : 0.15) : 0.7}>
                <line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={color} strokeWidth={isHighlighted ? Math.min(e.weight + 2, 6) : Math.min(e.weight, 4) + 1} />
                <polygon points={`${x2},${y2} ${ax1},${ay1} ${ax2},${ay2}`} fill={color} />
                <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6}
                  textAnchor="middle" fontSize={9} fill={color} fontWeight={600}>
                  {RELATION_LABELS[e.type] || e.type}
                </text>
              </g>
            );
          })}

          {/* ノード */}
          {appearedAgents.map((name) => {
            const pos = nodePositions[name];
            if (!pos) return null;
            const nodeRadius = 20;
            const color = agentColorMap[name] || "#94a3b8";
            const hasAction = roundActions.some((a) => a.agent === name);
            const isSelected = selectedAgent === name;
            const dimmed = selectedAgent && !isSelected
              && !visibleEdges.some((e) => (e.from === selectedAgent && e.to === name) || (e.to === selectedAgent && e.from === name));

            return (
              <g key={name}
                onClick={() => setSelectedAgent(isSelected ? null : name)}
                className="cursor-pointer"
                opacity={dimmed ? 0.2 : 1}
              >
                <circle
                  cx={pos.x} cy={pos.y} r={nodeRadius}
                  fill={color} opacity={hasAction ? 0.9 : 0.5}
                  stroke={isSelected ? "#1e293b" : hasAction ? "#475569" : "none"}
                  strokeWidth={isSelected ? 3 : hasAction ? 1.5 : 0}
                />
                <text x={pos.x} y={pos.y + nodeRadius + 14}
                  textAnchor="middle" fontSize={10} fill="#475569" fontWeight={500}>
                  {name.length > 14 ? name.slice(0, 14) + ".." : name}
                </text>
              </g>
            );
          })}

          {/* 登場ノード数が0のとき */}
          {appearedAgents.length === 0 && (
            <text x={cx} y={cy} textAnchor="middle" fontSize={13} fill="#94a3b8">
              スライダーを進めるとステークホルダーが登場します
            </text>
          )}
        </svg>
      </div>

      {/* 凡例 */}
      <div className="flex flex-wrap gap-3 mt-3">
        {Object.entries(RELATION_LABELS)
          .filter(([k]) => visibleEdges.some((e) => e.type === k))
          .map(([type, label]) => (
            <div key={type} className="flex items-center gap-1 text-xs text-text-secondary">
              <span className="inline-block w-3 h-0.5" style={{ backgroundColor: RELATION_COLORS[type] }} />
              {label}
            </div>
          ))}
      </div>

      {/* ラウンドナラティブ */}
      {roundNarrative && (
        <p className="text-sm text-text-secondary mt-3 italic border-l-2 border-interactive pl-3">
          {roundNarrative}
        </p>
      )}

      {/* 選択エージェントの詳細パネル */}
      {selectedAgent && (
        <div className="mt-4 bg-surface-1 rounded-lg p-4 border border-border">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded-full"
                style={{ backgroundColor: agentColorMap[selectedAgent] || "#94a3b8" }} />
              <h4 className="text-sm font-semibold text-text-primary">{selectedAgent}</h4>
            </div>
            <button onClick={() => setSelectedAgent(null)}
              className="text-xs text-text-tertiary hover:text-text-secondary">閉じる</button>
          </div>

          {selectedAgentInfo?.description && (
            <p className="text-xs text-text-secondary mb-3">{selectedAgentInfo.description}</p>
          )}

          {/* このラウンドの行動 */}
          {selectedAgentActions.length > 0 ? (
            <div>
              <p className="text-xs font-medium text-text-tertiary mb-1">{selectedRound}ヶ月目の行動:</p>
              {selectedAgentActions.map((a, i) => (
                <div key={i} className="flex items-start gap-2 text-sm py-1">
                  <span className="text-xs px-1.5 py-0.5 rounded bg-surface-2 text-text-secondary shrink-0">
                    {ACTION_LABELS[a.type] || a.type}
                  </span>
                  <span className="text-text-secondary">{cleanDescription(a.description)}</span>
                  {a.reacting_to && (
                    <span className="text-xs text-interactive ml-1 shrink-0">
                      ← {a.reacting_to}への反応
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-text-tertiary">{selectedRound}ヶ月目は行動なし</p>
          )}

          {/* 関係 */}
          {(() => {
            const relations = visibleEdges.filter((e) => e.from === selectedAgent || e.to === selectedAgent);
            if (relations.length === 0) return null;
            return (
              <div className="mt-3 pt-3 border-t border-border">
                <p className="text-xs font-medium text-text-tertiary mb-1">関係:</p>
                {relations.map((rel, i) => {
                  const other = rel.from === selectedAgent ? rel.to : rel.from;
                  const direction = rel.from === selectedAgent ? "→" : "←";
                  return (
                    <div key={i} className="flex items-center gap-2 text-xs py-0.5">
                      <span className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: RELATION_COLORS[rel.type] }} />
                      <span className="text-text-secondary">
                        {direction} {other}（{RELATION_LABELS[rel.type]}）
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
