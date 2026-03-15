import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimulation } from "../api/client";
import RelationshipGraph from "../components/RelationshipGraph";
import ProgressBar from "../components/ProgressBar";
import MarketChart from "../components/MarketChart";
import AgentTable from "../components/AgentTable";
import SocialFeed from "../components/SocialFeed";

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
              <p className="text-xs text-text-tertiary mb-3">
                LLMがシナリオとエージェント行動を分析した定性的評価です。詳細はレポートをご覧ください。
              </p>
              <div className="space-y-2">
                {[
                  { key: "user_adoption", label: "市場浸透",
                    high: "ターゲット市場に広く受け入れられる見込みです",
                    mid: "一定の浸透は見込めますが、拡大には課題があります",
                    low: "市場への浸透は限定的と予測されます" },
                  { key: "competitive_pressure", label: "競合環境",
                    high: "競合の脅威が高く、差別化戦略が不可欠です",
                    mid: "一定の競合はありますが、対処可能な水準です",
                    low: "競合の脅威は低く、有利なポジションです" },
                  { key: "revenue_potential", label: "収益性",
                    high: "持続的な収益を生む可能性が高いと評価されます",
                    mid: "収益化は可能ですが、成長には追加の施策が必要です",
                    low: "現状のモデルでは収益化に課題があります" },
                  { key: "ecosystem_health", label: "エコシステム",
                    high: "連携サービスやコミュニティが活発で成長基盤があります",
                    mid: "エコシステムは発展途上です",
                    low: "エコシステムが未成熟で、単独での成長が求められます" },
                ].map(({ key, label, high, mid, low }) => {
                  const val = result.summary.final_market.dimensions?.[key] ?? 0;
                  const level = val >= 0.6 ? "高" : val >= 0.3 ? "中" : "低";
                  const badgeColor = val >= 0.6
                    ? "bg-positive-light text-positive"
                    : val >= 0.3
                      ? "bg-caution-light text-caution"
                      : "bg-negative-light text-negative";
                  const text = val >= 0.6 ? high : val >= 0.3 ? mid : low;
                  return (
                    <div key={key} className="flex items-center gap-3 py-1.5">
                      <span className="shrink-0 text-xs font-medium text-text-secondary w-20">{label}</span>
                      <span className={`shrink-0 inline-block w-7 text-center text-xs font-bold rounded px-1 py-0.5 ${badgeColor}`}>{level}</span>
                      <span className="text-sm text-text-secondary">{text}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <RelationshipGraph rounds={result.rounds} agents={result.summary.agents} />

            {/* OASIS Social Feed */}
            {result.social_feed && result.social_feed.length > 0 && (
              <SocialFeed feed={result.social_feed} />
            )}

            {/* OASIS Stats */}
            {result.summary.oasis_stats && (
              <div className="bg-surface-0 rounded-lg border border-border p-4">
                <h3 className="text-sm font-medium text-text-primary mb-2">OASIS Platform Activity</h3>
                <div className="grid grid-cols-4 gap-4 text-center">
                  {[
                    { label: "Posts", value: result.summary.oasis_stats.posts },
                    { label: "Comments", value: result.summary.oasis_stats.comments },
                    { label: "Likes", value: result.summary.oasis_stats.likes },
                    { label: "Follows", value: result.summary.oasis_stats.follows },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <p className="text-lg font-bold text-text-primary">{value}</p>
                      <p className="text-xs text-text-tertiary">{label}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <AgentTable agents={result.summary.agents} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <MarketChart rounds={result.rounds} title="サービスの成長指標の変化" dimensions={["user_adoption", "revenue_potential", "market_awareness", "ecosystem_health"]} />
              <MarketChart rounds={result.rounds} title="サービスを取り巻くリスクの変化" dimensions={["competitive_pressure", "regulatory_risk", "tech_maturity", "funding_climate"]} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}


