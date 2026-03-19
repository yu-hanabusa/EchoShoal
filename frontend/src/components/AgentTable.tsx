import { useState } from "react";
import type { AgentSummary } from "../api/types";
import AgentPersonaCard from "./AgentPersonaCard";

interface Props {
  agents: AgentSummary[];
  serviceName?: string;
}



export default function AgentTable({ agents, serviceName }: Props) {
  const [selectedAgent, setSelectedAgent] = useState<AgentSummary | null>(null);

  // 対象サービスを先頭にソート
  const sn = serviceName?.toLowerCase() || "";
  const sorted = [...agents].sort((a, b) => {
    const aIsTarget = sn && a.name.toLowerCase().includes(sn);
    const bIsTarget = sn && b.name.toLowerCase().includes(sn);
    if (aIsTarget && !bIsTarget) return -1;
    if (!aIsTarget && bIsTarget) return 1;
    return 0;
  });

  if (agents.length === 0) {
    return (
      <div className="bg-surface-0 rounded-lg border border-border p-5">
        <h3 className="text-sm font-medium text-text-primary mb-3">
          ステークホルダー一覧
        </h3>
        <p className="text-sm text-text-tertiary py-6 text-center">
          データがありません
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5 overflow-x-auto">
      <h3 className="text-sm font-medium text-text-primary mb-4">
        ステークホルダー一覧
        <span className="text-text-tertiary font-normal ml-2">（名前クリックでペルソナ詳細）</span>
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-tertiary">
            <th className="py-2 pr-3 font-medium">ステークホルダー</th>
            <th className="py-2 px-3 font-medium">種別</th>
            <th className="py-2 pl-3 font-medium text-right" title="このステークホルダーの組織内の従業員・メンバー数">組織規模</th>
          </tr>
        </thead>
        <tbody className="text-text-primary">
          {sorted.map((agent) => (
            <tr
              key={agent.id}
              className="border-b border-border last:border-b-0 hover:bg-surface-1 transition-colors"
            >
              <td className="py-2.5 pr-3">
                <button
                  onClick={() => setSelectedAgent(agent)}
                  className="text-interactive font-semibold underline underline-offset-2 hover:text-interactive-hover bg-transparent border-none cursor-pointer p-0"
                >
                  {agent.name || "\u2014"}
                </button>
                {agent.description && (
                  <p className="text-xs text-text-tertiary mt-0.5 truncate max-w-[300px]">{agent.description}</p>
                )}
              </td>
              <td className="py-2.5 px-3">
                <span className="inline-block px-2 py-0.5 rounded text-xs bg-surface-2 text-text-secondary">
                  {agent.type}
                </span>
              </td>
              <td className="py-2.5 pl-3 text-right tabular-nums">
                {agent.headcount > 0 ? `${agent.headcount.toLocaleString()}名` : "\u2014"}
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
