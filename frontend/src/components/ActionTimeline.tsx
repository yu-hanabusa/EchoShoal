import { useState } from "react";
import type { RoundResult } from "../api/types";

const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

interface Props {
  rounds: RoundResult[];
}

export default function ActionTimeline({ rounds }: Props) {
  const [selectedRound, setSelectedRound] = useState<number | null>(null);

  // エージェント一覧を収集
  const agentSet = new Set<string>();
  for (const r of rounds) {
    for (const a of r.actions_taken) {
      if (a.agent) {
        agentSet.add(a.agent);
      }
    }
  }
  const agents = Array.from(agentSet);
  const agentColorMap: Record<string, string> = {};
  agents.forEach((a, i) => { agentColorMap[a] = AGENT_COLORS[i % AGENT_COLORS.length]; });

  // ラウンドごとのエージェント行動マップ
  const roundActions: Record<number, Record<string, { type: string; description: string; reacting_to?: string }[]>> = {};
  for (const r of rounds) {
    roundActions[r.round_number] = {};
    for (const a of r.actions_taken) {
      if (!roundActions[r.round_number][a.agent]) {
        roundActions[r.round_number][a.agent] = [];
      }
      roundActions[r.round_number][a.agent].push({
        type: a.type,
        description: a.description,
        reacting_to: a.reacting_to,
      });
    }
  }

  const displayRounds = rounds.filter((r) => r.actions_taken.length > 0);

  return (
    <div>
      {/* Agent Legend */}
      <div className="flex flex-wrap gap-3 mb-4">
        {agents.map((agent) => {
          return (
            <div key={agent} className="flex items-center gap-1.5 text-xs text-text-secondary">
              <span
                className="inline-block rounded-full shrink-0 w-3 h-3"
                style={{ backgroundColor: agentColorMap[agent] }}
              />
              {agent}
            </div>
          );
        })}
      </div>

      {/* Timeline Grid */}
      <div className="overflow-x-auto">
        <div className="min-w-[600px]">
          {/* Header: round numbers */}
          <div className="flex border-b border-border pb-2 mb-1">
            <div className="w-32 shrink-0 text-xs text-text-tertiary font-medium">エージェント</div>
            <div className="flex-1 flex">
              {displayRounds.map((r) => (
                <div
                  key={r.round_number}
                  className={`flex-1 text-center text-xs cursor-pointer transition-colors ${
                    selectedRound === r.round_number
                      ? "text-interactive font-bold"
                      : "text-text-tertiary hover:text-text-secondary"
                  }`}
                  onClick={() => setSelectedRound(
                    selectedRound === r.round_number ? null : r.round_number
                  )}
                >
                  R{r.round_number}
                </div>
              ))}
            </div>
          </div>

          {/* Agent rows */}
          {agents.map((agent) => (
            <div key={agent} className="flex items-center border-b border-border/50 py-1.5">
              <div className="w-32 shrink-0 text-xs text-text-secondary truncate pr-2 flex items-center gap-1.5">
                <span
                  className="inline-block w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: agentColorMap[agent] }}
                />
                {agent}
              </div>
              <div className="flex-1 flex">
                {displayRounds.map((r) => {
                  const actions = roundActions[r.round_number]?.[agent] || [];
                  const isSelected = selectedRound === r.round_number;
                  return (
                    <div
                      key={r.round_number}
                      className="flex-1 flex justify-center"
                    >
                      {actions.length > 0 ? (
                        <div
                          className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-[9px] font-bold cursor-pointer transition-transform ${
                            isSelected ? "scale-150 ring-2 ring-interactive" : "hover:scale-125"
                          }`}
                          style={{ backgroundColor: agentColorMap[agent] }}
                          title={actions.map((a) => `${a.type}: ${a.description}`).join("\n")}
                          onClick={() => setSelectedRound(
                            selectedRound === r.round_number ? null : r.round_number
                          )}
                        >
                          {actions.length}
                        </div>
                      ) : (
                        <div className="w-5 h-5 flex items-center justify-center">
                          <div className="w-1 h-1 rounded-full bg-border" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Selected Round Detail */}
      {selectedRound && (
        <div className="mt-4 bg-surface-1 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-text-primary">
              ラウンド {selectedRound} の詳細
            </h4>
            <button
              onClick={() => setSelectedRound(null)}
              className="text-xs text-text-tertiary hover:text-text-secondary"
            >
              閉じる
            </button>
          </div>

          {/* Round narrative */}
          {rounds.find((r) => r.round_number === selectedRound)?.summary && (
            <p className="text-sm text-text-secondary mb-3 italic border-l-2 border-interactive pl-3">
              {rounds.find((r) => r.round_number === selectedRound)?.summary}
            </p>
          )}

          {/* Actions */}
          <div className="space-y-2">
            {Object.entries(roundActions[selectedRound] || {}).map(([agent, actions]) => (
              <div key={agent}>
                {actions.map((action, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm py-1 flex-wrap">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full mt-1 shrink-0"
                      style={{ backgroundColor: agentColorMap[agent] }}
                    />
                    <span className="font-medium text-text-primary shrink-0">{agent}</span>
                    <span className="text-text-tertiary">→</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-surface-2 text-text-secondary font-mono shrink-0">
                      {action.type}
                    </span>
                    <span className="text-text-secondary">{action.description}</span>
                    {action.reacting_to && (
                      <span className="flex items-center gap-1 text-xs text-interactive ml-1">
                        <span>⟵</span>
                        <span
                          className="inline-block w-2 h-2 rounded-full"
                          style={{ backgroundColor: agentColorMap[action.reacting_to] || "#94a3b8" }}
                        />
                        <span className="font-medium">{action.reacting_to}</span>
                        <span className="text-text-tertiary">への反応</span>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* Events */}
          {(() => {
            const roundData = rounds.find((r) => r.round_number === selectedRound);
            if (!roundData?.events.length) return null;
            return (
              <div className="mt-3 pt-3 border-t border-border">
                <p className="text-xs font-medium text-text-tertiary mb-1">イベント</p>
                {roundData.events.map((e, i) => (
                  <p key={i} className="text-xs text-caution">{e}</p>
                ))}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
