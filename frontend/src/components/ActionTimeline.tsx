import { useState } from "react";
import type { ActionTaken, ActionVisibility, RoundResult } from "../api/types";

const VISIBILITY_STYLES: Record<ActionVisibility, { bg: string; text: string; label: string }> = {
  public: { bg: "#dcfce7", text: "#166534", label: "Public" },
  private: { bg: "#fee2e2", text: "#991b1b", label: "Private" },
  partial: { bg: "#fef3c7", text: "#92400e", label: "Partial" },
};

interface Props {
  rounds: RoundResult[];
}

export default function ActionTimeline({ rounds }: Props) {
  const [filter, setFilter] = useState<"all" | ActionVisibility>("all");
  const [agentFilter, setAgentFilter] = useState<string>("all");

  const agents = Array.from(new Set(rounds.flatMap((r) => r.actions_taken.map((a) => a.agent))));

  const filteredRounds = rounds.map((round) => ({
    ...round,
    actions_taken: round.actions_taken.filter((a) => {
      if (filter !== "all" && a.visibility !== filter) return false;
      if (agentFilter !== "all" && a.agent !== agentFilter) return false;
      return true;
    }),
  })).filter((r) => r.actions_taken.length > 0);

  return (
    <div>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as "all" | ActionVisibility)}
          style={{ padding: "0.375rem 0.75rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
        >
          <option value="all">All Visibility</option>
          <option value="public">Public Only</option>
          <option value="private">Private Only</option>
          <option value="partial">Partial Only</option>
        </select>

        <select
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
          style={{ padding: "0.375rem 0.75rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
        >
          <option value="all">All Agents</option>
          {agents.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      <div style={{ borderLeft: "3px solid #e5e7eb", paddingLeft: "1.5rem", marginLeft: "0.5rem" }}>
        {filteredRounds.map((round) => (
          <div key={round.round_number} style={{ marginBottom: "1.5rem" }}>
            <div style={{
              position: "relative",
              fontWeight: 700,
              fontSize: "0.875rem",
              color: "#6b7280",
              marginBottom: "0.5rem",
            }}>
              <span style={{
                position: "absolute",
                left: "-2.25rem",
                width: "12px",
                height: "12px",
                borderRadius: "50%",
                backgroundColor: "#3b82f6",
                top: "2px",
              }} />
              Round {round.round_number}
            </div>

            {round.actions_taken.map((action, i) => (
              <ActionCard key={`${round.round_number}-${i}`} action={action} />
            ))}

            {round.events.length > 0 && (
              <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                {round.events.map((e, i) => <div key={i}>{e}</div>)}
              </div>
            )}
          </div>
        ))}
      </div>

      {filteredRounds.length === 0 && (
        <p style={{ color: "#9ca3af", textAlign: "center" }}>No actions match the filter.</p>
      )}
    </div>
  );
}

function ActionCard({ action }: { action: ActionTaken }) {
  const vis = VISIBILITY_STYLES[action.visibility] || VISIBILITY_STYLES.public;

  return (
    <div style={{
      display: "flex",
      alignItems: "flex-start",
      gap: "0.5rem",
      padding: "0.5rem 0.75rem",
      marginBottom: "0.25rem",
      backgroundColor: "#f9fafb",
      borderRadius: "4px",
      fontSize: "0.875rem",
    }}>
      <span style={{
        display: "inline-block",
        padding: "0.125rem 0.375rem",
        borderRadius: "9999px",
        fontSize: "0.625rem",
        fontWeight: 600,
        backgroundColor: vis.bg,
        color: vis.text,
        flexShrink: 0,
        marginTop: "2px",
      }}>
        {vis.label}
      </span>
      <span style={{ fontWeight: 600, flexShrink: 0 }}>{action.agent}</span>
      <span style={{ color: "#4b5563" }}>
        <code style={{ fontSize: "0.75rem", backgroundColor: "#e5e7eb", padding: "0.125rem 0.25rem", borderRadius: "2px" }}>
          {action.type}
        </code>
        {" "}{action.description}
      </span>
    </div>
  );
}
