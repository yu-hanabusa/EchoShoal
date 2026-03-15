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
          <>
            <ProgressBar
              percentage={data.progress?.percentage ?? 0}
              currentRound={data.progress?.current_round ?? 0}
              totalRounds={data.progress?.total_rounds ?? 1}
              status={data.status}
              phase={data.progress?.phase}
            />
            <p className="text-xs text-text-tertiary text-center">
              ページを離れても処理はバックグラウンドで継続します
            </p>
          </>
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
            {/* サマリーカード */}
            <div className="bg-surface-0 rounded-lg border border-border p-6">
              <div className="flex items-baseline justify-between mb-4">
                <h2 className="text-sm font-semibold text-text-primary">シミュレーション概要</h2>
                <span className="text-xs text-text-tertiary">
                  {result.summary.total_rounds}ヶ月間 / {result.summary.agents.length}ステークホルダー
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { key: "user_adoption", label: "市場浸透度", desc: "ターゲット市場でのサービス認知・利用の広がり" },
                  { key: "competitive_pressure", label: "競合脅威度", desc: "競合からの参入・対抗の強さ" },
                  { key: "revenue_potential", label: "収益性見通し", desc: "持続的に収益を生む可能性" },
                  { key: "ecosystem_health", label: "エコシステム成熟度", desc: "連携サービス・コミュニティの活性度" },
                ].map(({ key, label, desc }) => {
                  const val = result.summary.final_market.dimensions?.[key] ?? 0;
                  const color = val >= 0.6 ? "text-positive" : val >= 0.3 ? "text-caution" : "text-negative";
                  const level = val >= 0.7 ? "高" : val >= 0.4 ? "中" : "低";
                  return (
                    <div key={key} className="text-center" title={desc}>
                      <p className="text-xs text-text-tertiary mb-1">{label}</p>
                      <p className={`text-2xl font-bold tabular-nums ${color}`}>{level}</p>
                      <p className="text-[10px] text-text-tertiary mt-0.5">{(val * 10).toFixed(1)} / 10</p>
                    </div>
                  );
                })}
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


