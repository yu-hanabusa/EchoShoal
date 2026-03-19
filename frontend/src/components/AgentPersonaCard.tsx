import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import type { AgentPersonality, AgentSummary } from "../api/types";

const PERSONALITY_LABELS: Record<string, string> = {
  conservatism: "保守性",
  bandwagon: "同調性",
  overconfidence: "過信度",
  sunk_cost_bias: "サンクコスト",
  info_sensitivity: "情報感度",
  noise: "ノイズ",
};

interface Props {
  agent: AgentSummary;
  onClose: () => void;
}

export default function AgentPersonaCard({ agent, onClose }: Props) {
  const personality = agent.personality;
  if (!personality) return null;

  const radarData = Object.entries(PERSONALITY_LABELS).map(([key, label]) => ({
    axis: label,
    value: personality[key as keyof AgentPersonality] as number,
  }));

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-surface-0 rounded-lg p-5 max-w-md w-[90%] max-h-[90vh] overflow-y-auto shadow-lg border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ヘッダー */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-base font-bold text-text-primary">{agent.name}</h3>
            <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-tertiary mt-1">
              {agent.stakeholder_type}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-text-tertiary hover:text-text-secondary text-lg leading-none"
          >✕</button>
        </div>

        {/* 説明 */}
        {agent.description && (
          <p className="text-xs text-text-secondary leading-relaxed mb-3">{agent.description}</p>
        )}

        {/* レーダーチャート */}
        <div className="w-full" style={{ height: 220 }}>
          <ResponsiveContainer>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="65%">
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: "#64748b" }} />
              <Radar
                dataKey="value"
                stroke="#4f46e5"
                fill="#4f46e5"
                fillOpacity={0.2}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* パーソナリティ説明 */}
        {personality.description && (
          <p className="text-xs text-text-secondary leading-relaxed mt-1 mb-3">
            {personality.description}
          </p>
        )}

        {/* 基本情報 */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-text-tertiary">
          <div>組織規模: <span className="text-text-secondary font-medium">{agent.headcount > 0 ? `${agent.headcount.toLocaleString()}名` : "—"}</span></div>
          <div>収益: <span className="text-text-secondary font-medium">{agent.revenue > 0 ? `${Math.round(agent.revenue).toLocaleString()}万円/月` : "—"}</span></div>
        </div>
      </div>
    </div>
  );
}
