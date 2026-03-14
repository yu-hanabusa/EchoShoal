import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimulation } from "../api/client";
import ProgressBar from "../components/ProgressBar";
import MarketChart from "../components/MarketChart";
import AgentTable from "../components/AgentTable";

export default function SimulationPage() {
  const { jobId } = useParams<{ jobId: string }>();

  const { data, error, isLoading } = useQuery({
    queryKey: ["simulation", jobId],
    queryFn: () => getSimulation(jobId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
    enabled: !!jobId,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center">
        <p className="text-gray-400">読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{(error as Error).message}</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300">
            ホームに戻る
          </Link>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const isRunning = data.status === "queued" || data.status === "running";
  const isCompleted = data.status === "completed";
  const result = data.result;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-4 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-2xl font-bold tracking-tight">
            Echo<span className="text-blue-400">Shoal</span>
          </Link>
          {isCompleted && (
            <Link
              to={`/simulation/${jobId}/report`}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
            >
              レポート表示
            </Link>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {isRunning && (
          <ProgressBar
            percentage={data.progress?.percentage ?? 0}
            currentRound={data.progress?.current_round ?? 0}
            totalRounds={data.progress?.total_rounds ?? 1}
            status={data.status}
          />
        )}

        {data.status === "failed" && (
          <div className="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-300 text-center">
            シミュレーション失敗: {data.error}
          </div>
        )}

        {isCompleted && result && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Stat label="実行ラウンド" value={`${result.summary.total_rounds}ヶ月`} />
              <Stat label="エージェント" value={`${result.summary.agents.length}体`} />
              <Stat label="LLM呼び出し" value={`${result.summary.llm_calls}回`} />
              <Stat
                label="失業率"
                value={`${(result.summary.final_market.unemployment_rate * 100).toFixed(1)}%`}
              />
            </div>

            <MarketChart
              rounds={result.rounds}
              dataKey="skill_demand"
              title="スキル別需要推移"
              skills={["ai_ml", "cloud_infra", "web_backend", "legacy"]}
            />

            <MarketChart
              rounds={result.rounds}
              dataKey="unit_prices"
              title="スキル別単価推移（万円/月）"
              skills={["ai_ml", "cloud_infra", "web_backend", "legacy"]}
            />

            <AgentTable agents={result.summary.agents} />
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 text-center">
      <p className="text-gray-400 text-sm">{label}</p>
      <p className="text-2xl font-bold text-gray-100 mt-1">{value}</p>
    </div>
  );
}
