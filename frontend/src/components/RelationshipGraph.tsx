import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, forceX, forceY } from "d3-force";
import { select } from "d3-selection";
import { drag as d3Drag } from "d3-drag";
import { zoom as d3Zoom } from "d3-zoom";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import type { RoundResult, AgentSummary, Relationship, AgentPersonality, SocialPost } from "../api/types";
import SocialFeed from "./SocialFeed";

const PERSONALITY_LABELS: Record<string, string> = {
  conservatism: "保守性",
  bandwagon: "同調性",
  overconfidence: "過信度",
  sunk_cost_bias: "サンクコスト",
  info_sensitivity: "情報感度",
  noise: "ノイズ",
};

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

/** 内部アクション（ユーザーに見せる必要がないもの） */
const HIDDEN_ACTIONS = new Set([
  "refresh", "sign_up", "login", "logout", "update_profile",
]);

/** 投稿内容をクリーンアップ */
function cleanDescription(raw: string): string {
  let s = raw;
  s = s.replace(/\(Impact:\s*[^)]*\)/gi, "");
  s = s.replace(/\[MARKET EVENT\][^\n]*/gi, "");
  s = s.replace(/\[COMMENT\]/gi, "");
  s = s.replace(/\[SEED\]/gi, "");
  s = s.replace(/New service alert:[^\n]*/gi, "");
  s = s.replace(/\{[^{}]*\}/g, "");
  s = s.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
  s = s.replace(/^(sign_up|refresh|login|logout|create_post|like|dislike|follow|unfollow|market_research|post_opinion|comment)\s*$/gm, "");
  s = s.replace(/\n{2,}/g, "\n").trim();
  return s;
}

/*
 * 関係タイプを4カテゴリに集約
 * 色はデザインシステムの意味的カラーに準拠:
 *   cooperative → positive (協力・成長)
 *   competitive → negative (競争・脅威)
 *   regulatory  → caution  (規制・注意)
 *   neutral     → neutral  (観察・中立)
 */
type RelationCategory = "cooperative" | "competitive" | "regulatory" | "neutral";

const CATEGORY_COLORS: Record<RelationCategory, string> = {
  cooperative: "#059669", // --positive
  competitive: "#e11d48", // --negative
  regulatory:  "#d97706", // --caution
  neutral:     "#64748b", // --neutral
};

const CATEGORY_LABELS: Record<RelationCategory, string> = {
  cooperative: "協力",
  competitive: "競争",
  regulatory:  "規制",
  neutral:     "観察",
};

const RELATION_TO_CATEGORY: Record<string, RelationCategory> = {
  partner: "cooperative", investor: "cooperative", advocate: "cooperative",
  support: "cooperative", amplification: "cooperative",
  competitor: "competitive", acquirer: "competitive", opposition: "competitive",
  critic: "competitive",
  regulator: "regulatory",
  user: "neutral", former_user: "neutral", interaction: "neutral",
  interest: "neutral", discussion: "neutral", reference: "neutral",
};

function getCategory(type: string): RelationCategory {
  return RELATION_TO_CATEGORY[type] || "neutral";
}

function PersonaAccordion({ agent }: { agent: AgentSummary }) {
  const [open, setOpen] = useState(false);
  const personality = agent.personality;
  if (!personality) return null;

  const radarData = Object.entries(PERSONALITY_LABELS).map(([key, label]) => ({
    axis: label,
    value: personality[key as keyof AgentPersonality] as number,
  }));

  return (
    <div className="pt-2 border-t border-border">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] font-medium text-text-tertiary hover:text-text-secondary w-full text-left py-1"
      >
        <span className="transition-transform" style={{ display: "inline-block", transform: open ? "rotate(90deg)" : "none" }}>▸</span>
        ペルソナ詳細
      </button>
      {open && (
        <div className="mt-1">
          <div className="w-full" style={{ height: 180 }}>
            <ResponsiveContainer>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="65%">
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="axis" tick={{ fontSize: 9, fill: "#64748b" }} />
                <Radar
                  dataKey="value"
                  stroke="#4f46e5"
                  fill="#4f46e5"
                  fillOpacity={0.2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          {personality.description && (
            <p className="text-[10px] text-text-secondary leading-relaxed mt-1 mb-2">
              {personality.description}
            </p>
          )}
          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] text-text-tertiary">
            <div>組織規模: <span className="text-text-secondary font-medium">{agent.headcount > 0 ? `${agent.headcount.toLocaleString()}名` : "—"}</span></div>
            <div>収益: <span className="text-text-secondary font-medium">{agent.revenue > 0 ? `${Math.round(agent.revenue).toLocaleString()}万円/月` : "—"}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}

interface Props {
  rounds: RoundResult[];
  agents: AgentSummary[];
  serviceName?: string;
  initialRelationships?: Relationship[];
  socialFeed?: SocialPost[];
}

interface Edge {
  from: string;
  to: string;
  type: string;
  category: RelationCategory;
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
  isTarget: boolean;
}

interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
  type: string;
  category: RelationCategory;
  weight: number;
}

const WIDTH = 700;
const HEIGHT = 500;

export default function RelationshipGraph({ rounds, agents, serviceName, initialRelationships, socialFeed }: Props) {
  const totalRounds = rounds.length;
  const [selectedRound, setSelectedRound] = useState(totalRounds);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [feedOpen, setFeedOpen] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<ReturnType<typeof forceSimulation<SimNode>> | null>(null);

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

    if (initialRelationships) {
      for (const r of initialRelationships) {
        const key = `${r.from}→${r.to}→${r.type}`;
        edgeMap.set(key, { from: r.from, to: r.to, type: r.type, category: getCategory(r.type), round: 0, weight: r.weight || 1 });
      }
    }

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
            edgeMap.set(key, { from: a.agent, to: a.reacting_to, type: relType, category: getCategory(relType), round: r.round_number, weight: 1 });
          }
        }
      }
    }

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
              edgeMap.set(key, { from: reactors[i], to: reactors[j], type: "discussion", category: "neutral", round: r.round_number, weight: 1 });
            }
          }
        }
      }
    }

    return Array.from(edgeMap.values());
  }, [rounds, TYPE_MAP, initialRelationships]);

  // 選択ラウンドまでの登場エージェント
  const appearedAgents = useMemo(() => {
    const appeared = new Set<string>();
    const sn = (serviceName || "").toLowerCase();
    if (sn) {
      const target = agents.find((a) => a.name.toLowerCase() === sn);
      if (target) appeared.add(target.name);
    }
    if (initialRelationships) {
      for (const r of initialRelationships) {
        appeared.add(r.from);
        appeared.add(r.to);
      }
    }
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

  // 今月アクティブなエージェント
  const activeAgentsThisRound = useMemo(() => {
    const active = new Set<string>();
    for (const a of roundActions) {
      if (!HIDDEN_ACTIONS.has(a.type)) active.add(a.agent);
    }
    return active;
  }, [roundActions]);

  const roundNarrative = (rounds.find((r) => r.round_number === selectedRound)?.summary || "")
    .replace(/ラウンド\s*(\d+)/g, "$1ヶ月目")
    .replace(/[Rr]ound\s*(\d+)/g, "$1ヶ月目");

  // 全エージェント名
  const allAgentNames = useMemo(() => {
    const names = new Set<string>();
    if (serviceName) names.add(serviceName);
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
  }, [rounds, serviceName, initialRelationships]);

  // D3 force simulation
  const initGraph = useCallback(() => {
    if (!svgRef.current) return;

    const svg = select(svgRef.current);
    svg.selectAll("*").remove();

    const sn = (serviceName || "").toLowerCase();
    const nodeCount = allAgentNames.length;

    const nodes: SimNode[] = allAgentNames.map((name) => ({
      id: name,
      x: WIDTH / 2 + (Math.random() - 0.5) * 300,
      y: HEIGHT / 2 + (Math.random() - 0.5) * 300,
      isTarget: sn ? name.toLowerCase() === sn : false,
    }));

    const nodeIds = new Set(nodes.map((n) => n.id));
    const links: SimLink[] = allEdges
      .filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to))
      .map((e) => ({ source: e.from, target: e.to, type: e.type, category: e.category, weight: e.weight }));

    if (nodes.length === 0) {
      svg.append("text")
        .attr("x", WIDTH / 2).attr("y", HEIGHT / 2)
        .attr("text-anchor", "middle").attr("font-size", 13).attr("fill", "#94a3b8")
        .text("シミュレーションデータがありません");
      return;
    }

    // ノード数に応じた反発力
    const chargeStrength = nodeCount > 15 ? -250 : nodeCount > 8 ? -350 : -450;

    const simulation = forceSimulation<SimNode>(nodes)
      .force("link", forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance(120)
      )
      .force("charge", forceManyBody<SimNode>().strength(chargeStrength))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide<SimNode>(35))
      .force("x", forceX<SimNode>(WIDTH / 2).strength(0.04))
      .force("y", forceY<SimNode>(HEIGHT / 2).strength(0.04));

    simulationRef.current = simulation;

    const targetNode = nodes.find((n) => n.isTarget);
    if (targetNode) { targetNode.fx = WIDTH / 2; targetNode.fy = HEIGHT / 2; }

    const g = svg.append("g").attr("class", "graph-root");
    svg.call(d3Zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on("zoom", (event) => { g.attr("transform", event.transform); }));

    // エッジ — 全て同一色。関係の種類は詳細パネルで表示
    g.append("g").attr("class", "links").selectAll("line")
      .data(links).join("line")
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 1)
      .attr("stroke-opacity", 0)
      .attr("stroke-dasharray", "3 3");

    // ノード
    const nodeEls = g.append("g").attr("class", "nodes")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes).join("circle")
      .attr("r", (d) => d.isTarget ? 24 : 14)
      .attr("fill", (d) => d.isTarget ? "#4f46e5" : "#475569")
      .attr("stroke", (d) => d.isTarget ? "#312e81" : "#e2e8f0")
      .attr("stroke-width", (d) => d.isTarget ? 2.5 : 1.5)
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

    // ラベル — 対象サービスのみ常時表示、他はupdateVisibilityで制御
    g.append("g").attr("class", "node-labels").selectAll("text")
      .data(nodes).join("text")
      .attr("text-anchor", "middle")
      .attr("font-size", (d) => d.isTarget ? 11 : 9)
      .attr("font-weight", (d) => d.isTarget ? 700 : 500)
      .attr("fill", "#334155")
      .attr("opacity", 0)
      .text((d) => d.id.length > 14 ? d.id.slice(0, 14) + ".." : d.id);

    // Tick
    simulation.on("tick", () => {
      g.select(".links").selectAll<SVGLineElement, SimLink>("line")
        .attr("x1", (d) => (d.source as SimNode).x).attr("y1", (d) => (d.source as SimNode).y)
        .attr("x2", (d) => (d.target as SimNode).x).attr("y2", (d) => (d.target as SimNode).y);

      g.select(".nodes").selectAll<SVGCircleElement, SimNode>("circle")
        .attr("cx", (d) => d.x).attr("cy", (d) => d.y);

      g.select(".node-labels").selectAll<SVGTextElement, SimNode>("text")
        .attr("x", (d) => d.x).attr("y", (d) => d.y + (d.isTarget ? 34 : 24));
    });
  }, [allAgentNames, allEdges, serviceName]);

  // 初回のみsimulation生成
  useEffect(() => {
    initGraph();
    return () => { simulationRef.current?.stop(); };
  }, [initGraph]);

  // ラウンド/選択変更時: ノード/エッジの表示を更新
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = select(svgRef.current);
    const g = svg.select(".graph-root");
    if (g.empty()) return;

    const appearedSet = new Set(appearedAgents);
    const visibleEdgeKeys = new Set(visibleEdges.map((e) => `${e.from}→${e.to}→${e.type}`));
    const hasSelection = !!selectedAgent;
    const relatedToSelected = new Set<string>();
    if (hasSelection) {
      for (const e of visibleEdges) {
        if (e.from === selectedAgent || e.to === selectedAgent) {
          relatedToSelected.add(e.from);
          relatedToSelected.add(e.to);
        }
      }
    }

    // ノード表示
    g.select(".nodes").selectAll<SVGCircleElement, SimNode>("circle")
      .attr("opacity", (d) => {
        if (!appearedSet.has(d.id)) return 0;
        if (d.isTarget) return 1;
        if (hasSelection) {
          if (d.id === selectedAgent) return 1;
          if (relatedToSelected.has(d.id)) return 0.8;
          return 0.15;
        }
        // アクティブ/非アクティブの区別
        return activeAgentsThisRound.has(d.id) ? 1 : 0.4;
      })
      .attr("r", (d) => {
        if (d.isTarget) return 24;
        if (hasSelection && d.id === selectedAgent) return 18;
        return activeAgentsThisRound.has(d.id) ? 14 : 10;
      })
      .attr("fill", (d) => {
        if (d.isTarget) return "#4f46e5"; // --interactive
        if (hasSelection && d.id === selectedAgent) return "#0f172a"; // --text-primary
        return activeAgentsThisRound.has(d.id) ? "#475569" : "#94a3b8";
      })
      .attr("stroke", (d) => {
        if (d.isTarget) return "#312e81";
        if (hasSelection && d.id === selectedAgent) return "#4f46e5";
        return "#e2e8f0";
      })
      .attr("stroke-width", (d) => {
        if (d.isTarget) return 2.5;
        if (hasSelection && d.id === selectedAgent) return 2;
        return 1.5;
      });

    // ラベル表示 — 対象サービスと選択エージェントは常時、他は選択時の関連ノードのみ
    g.select(".node-labels").selectAll<SVGTextElement, SimNode>("text")
      .attr("opacity", (d) => {
        if (!appearedSet.has(d.id)) return 0;
        if (d.isTarget) return 1;
        if (hasSelection) {
          if (d.id === selectedAgent) return 1;
          if (relatedToSelected.has(d.id)) return 0.8;
          return 0;
        }
        return activeAgentsThisRound.has(d.id) ? 0.9 : 0;
      });

    // エッジ表示 — デフォルト点線薄、選択時関連は実線強調
    g.select(".links").selectAll<SVGLineElement, SimLink>("line")
      .each(function (d) {
        const el = select(this);
        const s = typeof d.source === "object" ? d.source.id : d.source;
        const t = typeof d.target === "object" ? d.target.id : d.target;
        const key = `${s}→${t}→${d.type}`;
        const isVisible = visibleEdgeKeys.has(key);

        if (!isVisible) {
          el.attr("stroke-opacity", 0);
          return;
        }

        const isRelated = hasSelection && (s === selectedAgent || t === selectedAgent);

        if (isRelated) {
          // 選択エージェントの関連エッジ: 実線、強調（色はカテゴリ別）
          el.attr("stroke", CATEGORY_COLORS[d.category])
            .attr("stroke-opacity", 0.6)
            .attr("stroke-width", 1.5)
            .attr("stroke-dasharray", null);
        } else if (hasSelection) {
          // 選択中だが無関係: さらに薄く
          el.attr("stroke", "#94a3b8")
            .attr("stroke-opacity", 0.08)
            .attr("stroke-width", 1)
            .attr("stroke-dasharray", "3 3");
        } else {
          // デフォルト: ニュートラル点線、薄い
          el.attr("stroke", "#94a3b8")
            .attr("stroke-opacity", 0.2)
            .attr("stroke-width", 1)
            .attr("stroke-dasharray", "3 3");
        }
      });

  }, [appearedAgents, visibleEdges, roundActions, selectedAgent, activeAgentsThisRound]);

  // 選択エージェントの情報
  const selectedAgentInfo = agents.find((a) => a.name === selectedAgent);
  const selectedAgentActions = roundActions.filter((a) => a.agent === selectedAgent);

  // 選択エージェントの関係一覧
  const selectedRelations = useMemo(() => {
    if (!selectedAgent) return [];
    return visibleEdges.filter((e) => e.from === selectedAgent || e.to === selectedAgent);
  }, [visibleEdges, selectedAgent]);

  const showSlider = totalRounds > 1;

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-text-primary">ステークホルダー関係図</h3>
        <span className="text-xs text-text-tertiary">
          {selectedRound}ヶ月目 / {totalRounds}ヶ月
        </span>
      </div>

      {/* タイムスライダー */}
      {showSlider && (
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => setSelectedRound(Math.max(1, selectedRound - 1))}
            disabled={selectedRound <= 1}
            className="text-xs px-2 py-1 rounded bg-surface-2 text-text-secondary hover:bg-border disabled:opacity-30 disabled:cursor-default"
          >◀</button>
          <input
            type="range" min={1} max={totalRounds} value={selectedRound}
            onChange={(e) => setSelectedRound(Number(e.target.value))}
            className="flex-1"
          />
          <button
            onClick={() => setSelectedRound(Math.min(totalRounds, selectedRound + 1))}
            disabled={selectedRound >= totalRounds}
            className="text-xs px-2 py-1 rounded bg-surface-2 text-text-secondary hover:bg-border disabled:opacity-30 disabled:cursor-default"
          >▶</button>
        </div>
      )}

      {/* メインエリア: グラフ + 詳細パネル横並び */}
      <div className="flex gap-4">
        {/* 左: グラフ (2/3) */}
        <div className="flex-[2] min-w-0">
          <div className="rounded-lg border border-border overflow-hidden bg-surface-1 relative">
            <svg ref={svgRef} width="100%" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} />
          </div>

          {/* ナラティブ */}
          {roundNarrative && (
            <p className="text-xs text-text-tertiary mt-2 pl-3 border-l-2 border-border leading-relaxed">
              {roundNarrative}
            </p>
          )}
        </div>

        {/* 右: 詳細パネル (1/3) */}
        <div className="flex-1 min-w-[200px] max-w-[280px]">
          {selectedAgent ? (
            <div className="bg-surface-1 rounded-lg p-3 border border-border h-full overflow-y-auto max-h-[520px]">
              {/* エージェント名 */}
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-text-primary truncate pr-2">{selectedAgent}</h4>
                <button onClick={() => setSelectedAgent(null)}
                  className="text-[10px] text-text-tertiary hover:text-text-secondary shrink-0">✕</button>
              </div>

              {/* タイプ表示 */}
              {selectedAgentInfo?.stakeholder_type && (
                <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-tertiary mb-2">
                  {selectedAgentInfo.stakeholder_type}
                </span>
              )}

              {/* 説明 */}
              {selectedAgentInfo?.description && (
                <p className="text-xs text-text-secondary mb-3 leading-relaxed">{selectedAgentInfo.description}</p>
              )}

              {/* 今月の行動 */}
              {selectedAgentActions.filter((a) => !HIDDEN_ACTIONS.has(a.type)).length > 0 ? (
                <div className="mb-3">
                  <p className="text-[10px] font-medium text-text-tertiary mb-1">{selectedRound}ヶ月目の行動</p>
                  <div className="space-y-1.5">
                    {selectedAgentActions.filter((a) => !HIDDEN_ACTIONS.has(a.type)).map((a, i) => {
                      const desc = cleanDescription(a.description);
                      if (!desc) return null;
                      return (
                        <div key={i} className="text-xs">
                          <span className="text-[10px] px-1 py-0.5 rounded bg-surface-2 text-text-tertiary mr-1">
                            {ACTION_LABELS[a.type] || a.type}
                          </span>
                          <span className="text-text-secondary">{desc}</span>
                          {a.reacting_to && (
                            <span className="text-[10px] text-interactive ml-1">← {a.reacting_to}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-[10px] text-text-tertiary mb-3">{selectedRound}ヶ月目は行動なし</p>
              )}

              {/* 関係 */}
              {selectedRelations.length > 0 && (
                <div className="pt-2 border-t border-border">
                  <p className="text-[10px] font-medium text-text-tertiary mb-1">関係</p>
                  <div className="space-y-0.5">
                    {selectedRelations.map((rel, i) => {
                      const other = rel.from === selectedAgent ? rel.to : rel.from;
                      const direction = rel.from === selectedAgent ? "→" : "←";
                      return (
                        <div key={i} className="flex items-center gap-1.5 text-xs">
                          <span className="w-1.5 h-1.5 rounded-full shrink-0"
                            style={{ backgroundColor: CATEGORY_COLORS[rel.category] }} />
                          <span className="text-text-secondary truncate">
                            {direction} {other}
                          </span>
                          <span className="text-[10px] text-text-tertiary shrink-0">
                            {CATEGORY_LABELS[rel.category]}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ペルソナ詳細（アコーディオン） */}
              {selectedAgentInfo?.personality && (
                <PersonaAccordion agent={selectedAgentInfo} />
              )}
            </div>
          ) : (
            <div className="bg-surface-1 rounded-lg p-4 border border-border h-full flex items-center justify-center">
              <p className="text-xs text-text-tertiary text-center">
                ノードをクリックして<br />詳細を表示
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ステークホルダーの議論（アコーディオン） */}
      {socialFeed && socialFeed.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border">
          <button
            onClick={() => setFeedOpen(!feedOpen)}
            className="flex items-center gap-1.5 text-xs font-medium text-text-tertiary hover:text-text-secondary w-full text-left py-1"
          >
            <span className="transition-transform" style={{ display: "inline-block", transform: feedOpen ? "rotate(90deg)" : "none" }}>▸</span>
            ステークホルダーの議論
            <span className="text-[10px] text-text-tertiary ml-1">{socialFeed.length}件</span>
          </button>
          {feedOpen && (
            <div className="mt-2">
              <SocialFeed feed={socialFeed} agents={agents} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
