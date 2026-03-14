import type { AgentSummary } from "../api/types";

interface Props {
  agents: AgentSummary[];
}

export default function AgentTable({ agents }: Props) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 overflow-x-auto">
      <h3 className="text-lg font-medium text-gray-200 mb-4">
        エージェント最終状態
      </h3>
      <table className="w-full text-sm text-gray-300">
        <thead>
          <tr className="border-b border-gray-700 text-left">
            <th className="py-2 px-3">名前</th>
            <th className="py-2 px-3">種別</th>
            <th className="py-2 px-3 text-right">人員</th>
            <th className="py-2 px-3 text-right">売上(万円)</th>
            <th className="py-2 px-3 text-right">満足度</th>
            <th className="py-2 px-3 text-right">評判</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr key={agent.id} className="border-b border-gray-800 hover:bg-gray-800/50">
              <td className="py-2 px-3 font-medium text-gray-100">{agent.name}</td>
              <td className="py-2 px-3">
                <span className="px-2 py-0.5 rounded-full text-xs bg-gray-800 text-gray-300">
                  {agent.type}
                </span>
              </td>
              <td className="py-2 px-3 text-right">{agent.headcount}</td>
              <td className="py-2 px-3 text-right">{agent.revenue.toFixed(0)}</td>
              <td className="py-2 px-3 text-right">
                <span className={agent.satisfaction >= 0.5 ? "text-green-400" : "text-red-400"}>
                  {(agent.satisfaction * 100).toFixed(0)}%
                </span>
              </td>
              <td className="py-2 px-3 text-right">
                <span className={agent.reputation >= 0.5 ? "text-blue-400" : "text-yellow-400"}>
                  {(agent.reputation * 100).toFixed(0)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
