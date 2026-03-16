import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, forceX, forceY } from "d3-force";
import { select } from "d3-selection";
import { drag as d3Drag } from "d3-drag";
import { zoom as d3Zoom } from "d3-zoom";
import type { RoundResult, AgentSummary, Relationship } from "../api/types";

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
  exit_investment: "投資撤退", post_opinion: "意見投稿",
  market_research: "市場調査", endorse: "支持表明", critique: "批評",
  amplify: "拡散", quote_opinion: "引用", follow_stakeholder: "フォロー",
  dislike: "低評価",
};

/** 投稿内容をクリーンアップ */
/** 内部アクション（ユーザーに見せる必要がないもの） */
const HIDDEN_ACTIONS = new Set([
  "refresh", "sign_up", "login", "logout", "update_profile",
]);

/** 投稿内容をクリーンアップ */
function cleanDescription(raw: string): string {
  let s = raw;
  // (Impact: ...) タグ
  s = s.replace(/\(Impact:\s*[^)]*\)/gi, "");
  s = s.replace(/\[MARKET EVENT\]/gi, "");
  // JSON文字列全体 {"key": ...}
  s = s.replace(/\{[^}]*\}/g, "");
  // Unicodeエスケープ
  s = s.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
  // 英語のrawアクション名の行
  s = s.replace(/^(sign_up|refresh|login|logout|create_post|like|dislike|follow|unfollow|market_research|post_opinion|comment)\s*$/gm, "");
  // 残った空行
  s = s.replace(/\n{2,}/g, "\n").trim();
  return s;
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
  interest: "#60a5fa", discussion: "#a78bfa", amplification: "#fbbf24",
  support: "#34d399", opposition: "#ef4444", reference: "#06b6d4",
};

const RELATION_LABELS: Record<string, string> = {
  competitor: "競合", partner: "提携", investor: "投資",
  regulator: "規制", acquirer: "買収", user: "利用",
  advocate: "推薦", critic: "批判", former_user: "離脱",
  interaction: "影響",
  interest: "関心", discussion: "議論", amplification: "拡散",
  support: "支持", opposition: "反対", reference: "引用",
};

interface Props {
  rounds: RoundResult[];
  agents: AgentSummary[];
  serviceName?: string;
  initialRelationships?: Relationship[];
}

interface Edge {
  from: string;
  to: string;
  type: string;
  round: number;
  weight: number;
}

interface SimNode {
  id: string;
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
  color: string;
  isTarget: boolean;
  hasAction: boolean;
}

interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
  type: string;
  weight: number;
}

const WIDTH = 700;
const HEIGHT = 500;

export default function RelationshipGraph({ rounds, agents, serviceName, initialRelationships }: Props) {
  const totalRounds = rounds.length;
  const [selectedRound, setSelectedRound] = useState(totalRounds);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<ReturnType<typeof forceSimulation<SimNode>> | null>(null);

  const agentColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    agents.forEach((a, i) => { map[a.name] = AGENT_COLORS[i % AGENT_COLORS.length]; });
    return map;
  }, [agents]);

  const TYPE_MAP: Record<string, string> = useMemo(() => ({
    build_competitor: "competitor", launch_competing_product: "competitor",
    launch_competing_feature: "competitor", price_undercut: "competitor",
    partner: "partner", partner_integrate: "partner",
    invest_seed: "investor", invest_series: "investor", fund_competitor: "investor",
    regulate: "regulator", investigate: "regulator",
    acquire_service: "acquirer", acquire_startup: "acquirer",
    adopt_new_service: "user", adopt_service: "user", adopt_tool: "user",
    recommend: "advocate", complain: "critic", churn: "former_user",
    post_opinion: "discussion", comment: "discussion",
    endorse: "support", critique: "opposition", amplify: "amplification",
    quote_opinion: "reference", follow_stakeholder: "interest",
    market_research: "interest",
  }), []);

  // 全エッジ（3種統合: 初期関係 + アクションエッジ + 間接エッジ）
  const allEdges = useMemo(() => {
    const edgeMap = new Map<string, Edge>();

    // 1. 初期関係（round 0）
    if (initialRelationships) {
      for (const r of initialRelationships) {
        const key = `${r.from}→${r.to}→${r.type}`;
        edgeMap.set(key, { from: r.from, to: r.to, type: r.type, round: 0, weight: r.weight || 1 });
      }
    }

    // 2. アクションベースのエッジ（reacting_to）
    for (const r of rounds) {
      for (const a of r.actions_taken) {
        if (a.reacting_to) {
          const relType = TYPE_MAP[a.type] || "interaction";
          const key = `${a.agent}→${a.reacting_to}→${relType}`;
          const existing = edgeMap.get(key);
          if (existing) {
            existing.weight += 1;
            existing.round = Math.max(existing.round, r.round_number);
          } else {
            edgeMap.set(key, { from: a.agent, to: a.reacting_to, type: relType, round: r.round_number, weight: 1 });
          }
        }
      }
    }

    // 3. 間接エッジ（同一ラウンドで複数エージェントが同じ対象に反応）
    for (const r of rounds) {
      const targetGroups = new Map<string, string[]>();
      for (const a of r.actions_taken) {
        if (a.reacting_to) {
          const group = targetGroups.get(a.reacting_to) || [];
          group.push(a.agent);
          targetGroups.set(a.reacting_to, group);
        }
      }
      for (const [, reactors] of targetGroups) {
        if (reactors.length < 2) continue;
        for (let i = 0; i < reactors.length; i++) {
          for (let j = i + 1; j < reactors.length; j++) {
            const key = `${reactors[i]}→${reactors[j]}→discussion`;
            if (!edgeMap.has(key) && !edgeMap.has(`${reactors[j]}→${reactors[i]}→discussion`)) {
              edgeMap.set(key, { from: reactors[i], to: reactors[j], type: "discussion", round: r.round_number, weight: 1 });
            }
          }
        }
      }
    }

    return Array.from(edgeMap.values());
  }, [rounds, TYPE_MAP, initialRelationships]);

  // 選択ラウンドまでの登場エージェント（対象サービスは常に最初から表示）
  const appearedAgents = useMemo(() => {
    const appeared = new Set<string>();
    // 対象サービスは常に表示
    const sn = (serviceName || "").toLowerCase();
    if (sn) {
      const target = agents.find((a) => a.name.toLowerCase().includes(sn));
      if (target) appeared.add(target.name);
    }
    // 初期関係のエージェントも表示
    if (initialRelationships) {
      for (const r of initialRelationships) {
        appeared.add(r.from);
        appeared.add(r.to);
      }
    }
    // アクションベースの登場
    for (const r of rounds) {
      if (r.round_number > selectedRound) break;
      for (const a of r.actions_taken) {
        appeared.add(a.agent);
        if (a.reacting_to) appeared.add(a.reacting_to);
      }
    }
    return Array.from(appeared);
  }, [rounds, selectedRound, serviceName, agents, initialRelationships]);

  // 選択ラウンドまでのエッジ
  const visibleEdges = useMemo(() => {
    const filtered = allEdges.filter((e) => e.round <= selectedRound);
    const latest = new Map<string, Edge>();
    for (const e of filtered) latest.set(`${e.from}→${e.to}`, e);
    return Array.from(latest.values());
  }, [allEdges, selectedRound]);

  // 選択ラウンドの行動
  const roundActions = useMemo(() => {
    return rounds.find((r) => r.round_number === selectedRound)?.actions_taken || [];
  }, [rounds, selectedRound]);

  const roundNarrative = rounds.find((r) => r.round_number === selectedRound)?.summary || "";

  // 全エージェント名（simulation全体で登場する）
  const allAgentNames = useMemo(() => {
    const names = new Set<string>();
    const sn = (serviceName || "").toLowerCase();
    if (sn) {
      const target = agents.find((a) => a.name.toLowerCase().includes(sn));
      if (target) names.add(target.name);
    }
    if (initialRelationships) {
      for (const r of initialRelationships) { names.add(r.from); names.add(r.to); }
    }
    for (const r of rounds) {
      for (const a of r.actions_taken) {
        names.add(a.agent);
        if (a.reacting_to) names.add(a.reacting_to);
      }
    }
    return Array.from(names);
  }, [rounds, serviceName, agents, initialRelationships]);

  // D3 force simulation — 初回のみ生成、全ノード/全エッジを含む
  const initGraph = useCallback(() => {
    if (!svgRef.current) return;

    const svg = select(svgRef.current);
    svg.selectAll("*").remove();

    const sn = (serviceName || "").toLowerCase();

    // 全ノード
    const nodes: SimNode[] = allAgentNames.map((name) => ({
      id: name,
      x: WIDTH / 2 + (Math.random() - 0.5) * 300,
      y: HEIGHT / 2 + (Math.random() - 0.5) * 300,
      color: agentColorMap[name] || "#94a3b8",
      isTarget: sn ? name.toLowerCase().includes(sn) : false,
      hasAction: false,
    }));

    // 全エッジ
    const nodeIds = new Set(nodes.map((n) => n.id));
    const links: SimLink[] = allEdges
      .filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to))
      .map((e) => ({ source: e.from, target: e.to, type: e.type, weight: e.weight }));

    if (nodes.length === 0) {
      svg.append("text")
        .attr("x", WIDTH / 2).attr("y", HEIGHT / 2)
        .attr("text-anchor", "middle").attr("font-size", 13).attr("fill", "#94a3b8")
        .text("データがありません");
      return;
    }

    // Force simulation
    const simulation = forceSimulation<SimNode>(nodes)
      .force("link", forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance((d) => 120 + ((d as SimLink).weight - 1) * 30)
      )
      .force("charge", forceManyBody<SimNode>().strength(-350))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide<SimNode>(40))
      .force("x", forceX<SimNode>(WIDTH / 2).strength(0.04))
      .force("y", forceY<SimNode>(HEIGHT / 2).strength(0.04));

    simulationRef.current = simulation;

    const targetNode = nodes.find((n) => n.isTarget);
    if (targetNode) { targetNode.fx = WIDTH / 2; targetNode.fy = HEIGHT / 2; }

    const g = svg.append("g").attr("class", "graph-root");
    svg.call(d3Zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on("zoom", (event) => { g.attr("transform", event.transform); }));

    // エッジ
    g.append("g").attr("class", "links").selectAll("line")
      .data(links).join("line")
      .attr("stroke", (d) => RELATION_COLORS[d.type] || "#d1d5db")
      .attr("stroke-width", (d) => Math.min(d.weight + 1, 5))
      .attr("stroke-opacity", 0);

    g.append("g").attr("class", "link-labels").selectAll("text")
      .data(links).join("text")
      .attr("text-anchor", "middle").attr("font-size", 9)
      .attr("fill", (d) => RELATION_COLORS[d.type] || "#999")
      .attr("font-weight", 600).attr("opacity", 0)
      .text((d) => RELATION_LABELS[d.type] || "");

    // ノード
    const nodeEls = g.append("g").attr("class", "nodes")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes).join("circle")
      .attr("r", (d) => d.isTarget ? 28 : 18)
      .attr("fill", (d) => d.color)
      .attr("stroke", (d) => d.isTarget ? "#1e293b" : "#fff")
      .attr("stroke-width", (d) => d.isTarget ? 3 : 2)
      .attr("opacity", 0)
      .style("cursor", "pointer")
      .on("click", (_event, d) => { setSelectedAgent((prev) => prev === d.id ? null : d.id); });

    // ドラッグ
    nodeEls.call(d3Drag<SVGCircleElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        if (!d.isTarget) { d.fx = null; d.fy = null; }
      }));

    // ラベル
    g.append("g").attr("class", "node-labels").selectAll("text")
      .data(nodes).join("text")
      .attr("text-anchor", "middle")
      .attr("font-size", (d) => d.isTarget ? 11 : 10)
      .attr("font-weight", (d) => d.isTarget ? 700 : 500)
      .attr("fill", "#334155").attr("opacity", 0)
      .text((d) => d.id.length > 12 ? d.id.slice(0, 12) + ".." : d.id);

    // Tick
    simulation.on("tick", () => {
      const linkEls = g.select(".links").selectAll<SVGLineElement, SimLink>("line");
      linkEls
        .attr("x1", (d) => (d.source as SimNode).x).attr("y1", (d) => (d.source as SimNode).y)
        .attr("x2", (d) => (d.target as SimNode).x).attr("y2", (d) => (d.target as SimNode).y);

      const lblEls = g.select(".link-labels").selectAll<SVGTextElement, SimLink>("text");
      lblEls
        .attr("x", (d) => ((d.source as SimNode).x + (d.target as SimNode).x) / 2)
        .attr("y", (d) => ((d.source as SimNode).y + (d.target as SimNode).y) / 2 - 6);

      g.select(".nodes").selectAll<SVGCircleElement, SimNode>("circle")
        .attr("cx", (d) => d.x).attr("cy", (d) => d.y);

      g.select(".node-labels").selectAll<SVGTextElement, SimNode>("text")
        .attr("x", (d) => d.x).attr("y", (d) => d.y + (d.isTarget ? 38 : 28));
    });
  }, [allAgentNames, allEdges, agentColorMap, serviceName]);

  // 初回のみsimulation生成
  useEffect(() => {
    initGraph();
    return () => { simulationRef.current?.stop(); };
  }, [initGraph]);

  // ラウンド変更時: ノード/エッジの表示/非表示だけ切り替え（simulationは維持）
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = select(svgRef.current);
    const g = svg.select(".graph-root");
    if (g.empty()) return;

    const appearedSet = new Set(appearedAgents);
    const visibleEdgeKeys = new Set(visibleEdges.map((e) => `${e.from}→${e.to}→${e.type}`));
    const activeAgents = new Set(roundActions.map((a) => a.agent));

    // ノード表示切り替え
    g.select(".nodes").selectAll<SVGCircleElement, SimNode>("circle")
      .attr("opacity", (d) => appearedSet.has(d.id) ? (activeAgents.has(d.id) ? 0.9 : 0.5) : 0);

    g.select(".node-labels").selectAll<SVGTextElement, SimNode>("text")
      .attr("opacity", (d) => appearedSet.has(d.id) ? 1 : 0);

    // エッジ表示切り替え
    g.select(".links").selectAll<SVGLineElement, SimLink>("line")
      .attr("stroke-opacity", (d) => {
        const s = typeof d.source === "object" ? d.source.id : d.source;
        const t = typeof d.target === "object" ? d.target.id : d.target;
        const key = `${s}→${t}→${d.type}`;
        return visibleEdgeKeys.has(key) ? 0.6 : 0;
      });

    g.select(".link-labels").selectAll<SVGTextElement, SimLink>("text")
      .attr("opacity", (d) => {
        const s = typeof d.source === "object" ? d.source.id : d.source;
        const t = typeof d.target === "object" ? d.target.id : d.target;
        const key = `${s}→${t}→${d.type}`;
        return visibleEdgeKeys.has(key) ? 1 : 0;
      });
  }, [appearedAgents, visibleEdges, roundActions]);

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
          onClick={() => { setSelectedRound(Math.max(1, selectedRound - 1)); setSelectedAgent(null); }}
          className="text-xs px-2 py-1 rounded bg-surface-2 text-text-secondary hover:bg-border"
        >◀</button>
        <input
          type="range" min={1} max={totalRounds} value={selectedRound}
          onChange={(e) => { setSelectedRound(Number(e.target.value)); setSelectedAgent(null); }}
          className="flex-1"
        />
        <button
          onClick={() => { setSelectedRound(Math.min(totalRounds, selectedRound + 1)); setSelectedAgent(null); }}
          className="text-xs px-2 py-1 rounded bg-surface-2 text-text-secondary hover:bg-border"
        >▶</button>
      </div>

      {/* D3 Force Directed Graph */}
      <div className="rounded-lg border border-border overflow-hidden bg-surface-1">
        <svg ref={svgRef} width="100%" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} />
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

          {selectedAgentActions.filter((a) => !HIDDEN_ACTIONS.has(a.type)).length > 0 ? (
            <div>
              <p className="text-xs font-medium text-text-tertiary mb-1">{selectedRound}ヶ月目の行動:</p>
              {selectedAgentActions.filter((a) => !HIDDEN_ACTIONS.has(a.type)).map((a, i) => {
                const desc = cleanDescription(a.description);
                if (!desc) return null;
                return (
                <div key={i} className="flex items-start gap-2 text-sm py-1">
                  <span className="text-xs px-1.5 py-0.5 rounded bg-surface-2 text-text-secondary shrink-0">
                    {ACTION_LABELS[a.type] || a.type}
                  </span>
                  <span className="text-text-secondary">{desc}</span>
                  {a.reacting_to && (
                    <span className="text-xs text-interactive ml-1 shrink-0">
                      ← {a.reacting_to}への反応
                    </span>
                  )}
                </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-text-tertiary">{selectedRound}ヶ月目は行動なし</p>
          )}

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
