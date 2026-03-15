import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimulation } from "../api/client";
import ActionTimeline from "../components/ActionTimeline";
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
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <p className="text-text-tertiary text-sm">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-negative text-sm">{(error as Error).message}</p>
          <Link to="/" className="text-interactive hover:underline text-sm">Home</Link>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const isRunning = data.status === "queued" || data.status === "running";
  const isCompleted = data.status === "completed";
  const result = data.result;

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <Link to="/" className="text-sm text-text-tertiary hover:text-interactive">
            &larr; Simulations
          </Link>
          {isCompleted && (
            <Link
              to={`/simulation/${jobId}/report`}
              className="px-4 py-1.5 rounded-md bg-interactive hover:bg-interactive-hover text-white text-sm font-medium transition-colors"
            >
              View Report
            </Link>
          )}
        </div>

        {/* Running */}
        {isRunning && (
          <ProgressBar
            percentage={data.progress?.percentage ?? 0}
            currentRound={data.progress?.current_round ?? 0}
            totalRounds={data.progress?.total_rounds ?? 1}
            status={data.status}
          />
        )}

        {/* Failed */}
        {data.status === "failed" && (
          <div className="px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm" role="alert">
            Simulation failed
            {data.error && <span className="block mt-1 text-text-secondary">{data.error}</span>}
          </div>
        )}

        {/* Completed: Results */}
        {isCompleted && result && (
          <div className="space-y-6">
            <div className="bg-surface-0 rounded-lg border border-border p-6">
              <div className="flex flex-col md:flex-row md:items-end gap-6">
                <div className="flex-1">
                  <p className="text-sm text-text-tertiary mb-1">ユーザー獲得率</p>
                  <p className="text-4xl font-bold text-text-primary tabular-nums tracking-tight">
                    {((result.summary.final_market.dimensions?.user_adoption ?? 0) * 100).toFixed(1)}
                    <span className="text-lg font-normal text-text-secondary ml-0.5">%</span>
                  </p>
                </div>
                <div className="flex gap-8 text-sm">
                  <div>
                    <p className="text-text-tertiary">シミュレーション期間</p>
                    <p className="text-text-primary font-medium tabular-nums">{result.summary.total_rounds}ヶ月</p>
                  </div>
                  <div>
                    <p className="text-text-tertiary">エージェント数</p>
                    <p className="text-text-primary font-medium tabular-nums">{result.summary.agents.length}体</p>
                  </div>
                  <div>
                    <p className="text-text-tertiary">LLM判断回数</p>
                    <p className="text-text-primary font-medium tabular-nums">{result.summary.llm_calls.toLocaleString()}回</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <MarketChart rounds={result.rounds} title="市場ディメンション推移（成長系）" dimensions={["user_adoption", "revenue_potential", "market_awareness", "ecosystem_health"]} />
              <MarketChart rounds={result.rounds} title="市場ディメンション推移（圧力系）" dimensions={["competitive_pressure", "regulatory_risk", "tech_maturity", "funding_climate"]} />
            </div>

            <AgentTable agents={result.summary.agents} />

            <div className="bg-surface-0 rounded-lg border border-border p-5">
              <h3 className="text-sm font-medium text-text-primary mb-4">行動タイムライン</h3>
              <ActionTimeline rounds={result.rounds} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}


