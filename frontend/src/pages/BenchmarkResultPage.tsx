import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getEvaluationResult, getSimulation } from "../api/client";
import ProgressBar from "../components/ProgressBar";
import MarketChart from "../components/MarketChart";
import type {
  EvaluationResult,
  FullBenchmarkResult,
  ResearchData,
  TrendResult,
} from "../api/types";

function DirectionBadge({ direction, correct }: { direction: string; correct?: boolean }) {
  const arrow = direction === "up" ? "\u2191" : direction === "down" ? "\u2193" : "\u2192";
  const color = correct === undefined
    ? "text-text-tertiary"
    : correct
      ? "text-positive"
      : "text-negative";
  return <span className={`font-mono text-sm font-bold ${color}`}>{arrow}</span>;
}

function AccuracyBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? "bg-positive-light text-positive" : "bg-negative-light text-negative";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-sm font-bold ${color}`}>
      {pct}%
    </span>
  );
}

function ResearchSection({ research }: { research: ResearchData }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const reports = [
    { key: "market_report", label: "Market Report", content: research.market_report },
    { key: "user_behavior", label: "User Behavior", content: research.user_behavior },
    { key: "stakeholders", label: "Stakeholders", content: research.stakeholders },
  ];

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5 space-y-4">
      <h3 className="text-sm font-semibold text-text-primary">Market Research</h3>

      {/* Data source status */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Google Trends", count: research.trends_count },
          { label: "GitHub", count: research.github_repos_count },
          { label: "Yahoo Finance", count: research.finance_data_count },
        ].map(({ label, count }) => (
          <div key={label} className="flex items-center gap-2 text-xs">
            <span className={count > 0 ? "text-positive" : "text-text-tertiary"}>
              {count > 0 ? "\u2713" : "\u2717"}
            </span>
            <span className="text-text-secondary">{label}</span>
            {count > 0 && <span className="text-text-tertiary">({count})</span>}
          </div>
        ))}
      </div>

      {research.errors.length > 0 && (
        <div className="text-xs text-caution space-y-0.5">
          {research.errors.map((e, i) => (
            <p key={i}>{e}</p>
          ))}
        </div>
      )}

      {/* Collapsible reports */}
      <div className="space-y-2">
        {reports.map(({ key, label, content }) => (
          <div key={key} className="border border-border rounded-md">
            <button
              onClick={() => setExpanded(expanded === key ? null : key)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-1"
            >
              <span>{label}</span>
              <span>{expanded === key ? "\u25B2" : "\u25BC"}</span>
            </button>
            {expanded === key && content && (
              <div className="px-3 pb-3 text-xs text-text-secondary whitespace-pre-wrap max-h-80 overflow-y-auto">
                {content}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendTable({ trends }: { trends: TrendResult[] }) {
  const METRIC_LABELS: Record<string, string> = {
    "dimensions.user_adoption": "User Adoption",
    "dimensions.revenue_potential": "Revenue Potential",
    "dimensions.tech_maturity": "Tech Maturity",
    "dimensions.competitive_pressure": "Competitive Pressure",
    "dimensions.regulatory_risk": "Regulatory Risk",
    "dimensions.market_awareness": "Market Awareness",
    "dimensions.ecosystem_health": "Ecosystem Health",
    "dimensions.funding_climate": "Funding Climate",
    economic_sentiment: "Economic Sentiment",
    tech_hype_level: "Tech Hype",
    regulatory_pressure: "Regulatory Pressure",
    ai_disruption_level: "AI Disruption",
  };

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-3">Trend Evaluation</h3>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-text-tertiary border-b border-border">
            <th className="text-left py-1.5 font-medium">Metric</th>
            <th className="text-center py-1.5 font-medium">Expected</th>
            <th className="text-center py-1.5 font-medium">Actual</th>
            <th className="text-center py-1.5 font-medium">Change</th>
            <th className="text-center py-1.5 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {trends.map((t) => (
            <tr key={t.metric} className="border-b border-border/50">
              <td className="py-2 text-text-secondary">
                {METRIC_LABELS[t.metric] || t.metric}
              </td>
              <td className="py-2 text-center">
                <DirectionBadge direction={t.expected_direction} />
              </td>
              <td className="py-2 text-center">
                <DirectionBadge direction={t.actual_direction} correct={t.direction_correct} />
              </td>
              <td className="py-2 text-center text-text-tertiary font-mono">
                {t.actual_change_rate > 0 ? "+" : ""}
                {t.actual_change_rate.toFixed(1)}%
              </td>
              <td className="py-2 text-center">
                {t.direction_correct ? (
                  <span className="text-positive font-bold">PASS</span>
                ) : (
                  <span className="text-negative font-bold">FAIL</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EvaluationSection({ evaluation }: { evaluation: EvaluationResult }) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-surface-0 rounded-lg border border-border p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{evaluation.benchmark_name}</h3>
            <p className="text-xs text-text-tertiary mt-0.5">
              {evaluation.simulation_rounds}ヶ月 / {evaluation.execution_time_seconds.toFixed(1)}s
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-tertiary mb-1">Direction Accuracy</p>
            <AccuracyBadge value={evaluation.direction_accuracy} />
          </div>
        </div>
      </div>

      <TrendTable trends={evaluation.trend_results} />
    </div>
  );
}

export default function BenchmarkResultPage() {
  const { jobId } = useParams<{ jobId: string }>();

  // Poll evaluation job status
  const { data: evalData, error: evalError, isLoading: evalLoading } = useQuery({
    queryKey: ["evaluation", jobId],
    queryFn: () => getEvaluationResult(jobId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 3000 : false;
    },
    enabled: !!jobId,
  });

  // Once completed, fetch the simulation result (which has rounds, agents, social_feed)
  const simJobId = evalData?.result?.full_result
    ? undefined // Full result is self-contained
    : evalData?.status === "completed" ? jobId : undefined;

  const { data: _simData } = useQuery({
    queryKey: ["simulation-for-eval", simJobId],
    queryFn: () => getSimulation(simJobId!),
    enabled: false, // We get simulation data from the evaluation result's child job
  });

  if (evalLoading) {
    return (
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <p className="text-text-tertiary text-sm">Loading...</p>
      </div>
    );
  }

  if (evalError) {
    return (
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-negative text-sm">{(evalError as Error).message}</p>
          <Link to="/benchmarks" className="text-interactive hover:underline text-sm">Back</Link>
        </div>
      </div>
    );
  }

  if (!evalData) return null;

  const isRunning = evalData.status === "queued" || evalData.status === "running";
  const isCompleted = evalData.status === "completed";
  const isFailed = evalData.status === "failed";

  const fullResult = evalData.result?.full_result as FullBenchmarkResult | undefined;
  const evalOnly = evalData.result?.evaluation as EvaluationResult | undefined;
  const evaluation = fullResult?.evaluation || evalOnly;
  const research = fullResult?.research;


  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <Link to="/benchmarks" className="text-sm text-text-tertiary hover:text-interactive">
          &larr; Benchmarks
        </Link>

        {/* Running */}
        {isRunning && (
          <>
            <ProgressBar
              percentage={evalData.progress?.percentage ?? 0}
              currentRound={evalData.progress?.current_round ?? 0}
              totalRounds={evalData.progress?.total_rounds ?? 1}
              status={evalData.status}
              phase={evalData.progress?.phase}
            />
            <p className="text-xs text-text-tertiary text-center">
              {research !== undefined ? "市場調査 → シミュレーション → 評価" : "シミュレーション → 評価"}
            </p>
          </>
        )}

        {/* Failed */}
        {isFailed && (
          <div className="px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm" role="alert">
            Benchmark failed
            {evalData.error && <span className="block mt-1 text-text-secondary">{evalData.error}</span>}
          </div>
        )}

        {/* Completed */}
        {isCompleted && evaluation && (
          <div className="space-y-6">
            {/* Timing summary */}
            {fullResult && (
              <div className="bg-surface-0 rounded-lg border border-border p-4">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-lg font-bold text-text-primary">
                      {fullResult.research_time_seconds.toFixed(1)}s
                    </p>
                    <p className="text-xs text-text-tertiary">Market Research</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-text-primary">
                      {evaluation.execution_time_seconds.toFixed(1)}s
                    </p>
                    <p className="text-xs text-text-tertiary">Simulation</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-text-primary">
                      {fullResult.total_time_seconds.toFixed(1)}s
                    </p>
                    <p className="text-xs text-text-tertiary">Total</p>
                  </div>
                </div>
              </div>
            )}

            {/* Research data */}
            {research && <ResearchSection research={research} />}

            {/* Evaluation */}
            <EvaluationSection evaluation={evaluation} />

            {/* Dimension timelines as charts */}
            {evaluation.dimension_timelines.length > 0 && (
              <DimensionTimelineCharts timelines={evaluation.dimension_timelines} />
            )}
          </div>
        )}
      </main>
    </div>
  );
}

/** ディメンション推移をMarketChartと同じ形式で表示 */
function DimensionTimelineCharts({
  timelines,
}: {
  timelines: Array<{ dimension: string; values: number[] }>;
}) {
  // Convert timelines to RoundResult-like format for MarketChart
  if (timelines.length === 0 || timelines[0].values.length === 0) return null;

  const numRounds = timelines[0].values.length;
  const chartData = Array.from({ length: numRounds }, (_, i) => {
    const point: Record<string, number> = { round: i + 1 };
    for (const tl of timelines) {
      point[tl.dimension] = Number((tl.values[i] ?? 0).toFixed(3));
    }
    return point;
  });

  // Build fake RoundResult[] for MarketChart
  const fakeRounds = chartData.map((d) => ({
    round_number: d.round,
    market_state: {
      round_number: d.round,
      service_name: "",
      dimensions: Object.fromEntries(
        timelines.map((tl) => [tl.dimension, d[tl.dimension] ?? 0])
      ),
      economic_sentiment: 0,
      tech_hype_level: 0,
      regulatory_pressure: 0,
      remote_work_adoption: 0,
      ai_disruption_level: 0,
    },
    actions_taken: [],
    events: [],
  }));

  const growthDims = ["user_adoption", "revenue_potential", "market_awareness", "ecosystem_health"]
    .filter((d) => timelines.some((t) => t.dimension === d));
  const riskDims = ["competitive_pressure", "regulatory_risk", "tech_maturity", "funding_climate"]
    .filter((d) => timelines.some((t) => t.dimension === d));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {growthDims.length > 0 && (
        <MarketChart rounds={fakeRounds} title="Growth Metrics" dimensions={growthDims} />
      )}
      {riskDims.length > 0 && (
        <MarketChart rounds={fakeRounds} title="Risk Metrics" dimensions={riskDims} />
      )}
    </div>
  );
}
