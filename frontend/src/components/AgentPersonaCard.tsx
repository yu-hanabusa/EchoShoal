import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
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
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: "white",
          borderRadius: "8px",
          padding: "2rem",
          maxWidth: "500px",
          width: "90%",
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1.25rem" }}>{agent.name}</h3>
            <span style={{
              display: "inline-block",
              padding: "0.125rem 0.5rem",
              borderRadius: "9999px",
              fontSize: "0.75rem",
              backgroundColor: "#e0e7ff",
              color: "#4338ca",
              marginTop: "0.25rem",
            }}>
              {agent.type}
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              border: "none",
              background: "none",
              fontSize: "1.5rem",
              cursor: "pointer",
              color: "#9ca3af",
              lineHeight: 1,
            }}
          >
            x
          </button>
        </div>

        {agent.description && (
          <p style={{ color: "#6b7280", fontSize: "0.875rem", margin: "0 0 1rem" }}>
            {agent.description}
          </p>
        )}

        <div style={{ width: "100%", height: "280px" }}>
          <ResponsiveContainer>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
              <Radar
                dataKey="value"
                stroke="#4f46e5"
                fill="#4f46e5"
                fillOpacity={0.3}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {personality.description && (
          <div style={{
            marginTop: "1rem",
            padding: "0.75rem",
            backgroundColor: "#f8fafc",
            borderRadius: "4px",
            fontSize: "0.875rem",
            color: "#475569",
            lineHeight: 1.6,
          }}>
            {personality.description}
          </div>
        )}

        <div style={{ marginTop: "1rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.8rem" }}>
          <div>Revenue: <strong>{agent.revenue.toFixed(0)}</strong> /month</div>
          <div>Headcount: <strong>{agent.headcount}</strong></div>
          <div>Satisfaction: <strong>{(agent.satisfaction * 100).toFixed(0)}%</strong></div>
          <div>Reputation: <strong>{(agent.reputation * 100).toFixed(0)}%</strong></div>
        </div>
      </div>
    </div>
  );
}
