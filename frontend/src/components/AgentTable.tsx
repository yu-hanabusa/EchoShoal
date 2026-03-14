import { useState } from "react";
import type { AgentSummary } from "../api/types";
import AgentPersonaCard from "./AgentPersonaCard";

interface Props {
  agents: AgentSummary[];
}

function MetricCell({
  value,
  thresholds,
}: {
  value: number;
  thresholds: { good: number; bad: number };
}) {
  const pct = (value * 100).toFixed(0);
  const color =
    value >= thresholds.good
      ? "text-positive"
      : value < thresholds.bad
        ? "text-negative"
        : "text-text-primary";
  return <span className={`${color} tabular-nums`}>{pct}%</span>;
}

export default function AgentTable({ agents }: Props) {
  const [selectedAgent, setSelectedAgent] = useState<AgentSummary | null>(null);

  if (agents.length === 0) {
    return (
      <div className="bg-surface-0 rounded-lg border border-border p-5">
        <h3 className="text-sm font-medium text-text-primary mb-3">
          Agents
        </h3>
        <p className="text-sm text-text-tertiary py-6 text-center">
          No agent data.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5 overflow-x-auto">
      <h3 className="text-sm font-medium text-text-primary mb-4">
        Agents (click name for persona)
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-tertiary">
            <th className="py-2 pr-3 font-medium">Name</th>
            <th className="py-2 px-3 font-medium">Type</th>
            <th className="py-2 px-3 font-medium text-right">Headcount</th>
            <th className="py-2 px-3 font-medium text-right">Revenue</th>
            <th className="py-2 px-3 font-medium text-right">Satisfaction</th>
            <th className="py-2 pl-3 font-medium text-right">Reputation</th>
          </tr>
        </thead>
        <tbody className="text-text-primary">
          {agents.map((agent) => (
            <tr
              key={agent.id}
              className="border-b border-border last:border-b-0 hover:bg-surface-1 transition-colors"
            >
              <td className="py-2.5 pr-3 font-medium truncate max-w-[200px]">
                <button
                  onClick={() => setSelectedAgent(agent)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#4f46e5",
                    fontWeight: 600,
                    textDecoration: "underline",
                    textUnderlineOffset: "2px",
                    padding: 0,
                  }}
                >
                  {agent.name || "\u2014"}
                </button>
              </td>
              <td className="py-2.5 px-3">
                <span className="inline-block px-2 py-0.5 rounded text-xs bg-surface-2 text-text-secondary">
                  {agent.type}
                </span>
              </td>
              <td className="py-2.5 px-3 text-right tabular-nums">
                {agent.headcount.toLocaleString()}
              </td>
              <td className="py-2.5 px-3 text-right tabular-nums">
                {agent.revenue > 0 ? agent.revenue.toLocaleString() : "\u2014"}
              </td>
              <td className="py-2.5 px-3 text-right">
                <MetricCell
                  value={agent.satisfaction}
                  thresholds={{ good: 0.6, bad: 0.3 }}
                />
              </td>
              <td className="py-2.5 pl-3 text-right">
                <MetricCell
                  value={agent.reputation}
                  thresholds={{ good: 0.6, bad: 0.3 }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedAgent && (
        <AgentPersonaCard
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
        />
      )}
    </div>
  );
}
