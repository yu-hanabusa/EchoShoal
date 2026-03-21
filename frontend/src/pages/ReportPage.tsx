import { useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getReport, getPrediction } from "../api/client";
import { DIMENSION_LABELS, isThreatDimension } from "../api/types";
import ScoreGauge from "../components/ScoreGauge";
import RiskOpportunityCard from "../components/RiskOpportunityCard";
import DimensionRadar from "../components/DimensionRadar";
import DimensionSparkline from "../components/DimensionSparkline";
import SectionNav from "../components/SectionNav";

export default function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>();

  const reportQuery = useQuery({
    queryKey: ["report", jobId],
    queryFn: () => getReport(jobId!),
    enabled: !!jobId,
  });

  const predictionQuery = useQuery({
    queryKey: ["prediction", jobId],
    queryFn: () => getPrediction(jobId!),
    enabled: !!jobId,
  });

  const report = reportQuery.data;
  const prediction = predictionQuery.data;
  const isLoading = reportQuery.isLoading || predictionQuery.isLoading;
  const error = reportQuery.error || predictionQuery.error;

  // Build section nav items based on available data
  const navSections = useMemo(() => {
    const items: { id: string; label: string }[] = [];
    if (report?.success_score) items.push({ id: "score", label: "スコア" });
    if (report?.executive_summary) items.push({ id: "summary", label: "総合分析" });
    if (prediction?.dimension_predictions?.length) {
      items.push({ id: "dimensions", label: "指標分析" });
      items.push({ id: "trends", label: "トレンド" });
    }
    if (prediction?.highlights?.length) items.push({ id: "highlights", label: "ハイライト" });
    if (report?.sections?.length) {
      report.sections.forEach((s, i) =>
        items.push({ id: `section-${i}`, label: s.title }),
      );
    }
    return items;
  }, [report, prediction]);

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Back link */}
        <div className="flex justify-end">
          <Link
            to={`/simulation/${jobId}`}
            className="text-sm text-interactive hover:underline"
          >
            シミュレーション結果に戻る
          </Link>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="bg-surface-0 rounded-lg border border-border p-8 text-center">
            <p className="text-sm text-text-secondary">
              レポートを読み込み中...
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            className="px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm"
            role="alert"
          >
            {(error as Error).message}
          </div>
        )}

        {/* Section Navigation */}
        {!isLoading && !error && navSections.length > 0 && (
          <SectionNav sections={navSections} />
        )}

        {/* ─── Section: Success Score ─── */}
        {report?.success_score && (
          <section id="score" className="scroll-mt-16">
            <div className={`rounded-lg border p-6 ${
              report.success_score.score >= 70 ? "bg-positive/5 border-positive/30" :
              report.success_score.score >= 40 ? "bg-caution/5 border-caution/30" :
              "bg-negative/5 border-negative/30"
            }`}>
              {/* Gauge + verdict */}
              <div className="flex flex-col sm:flex-row items-center gap-6 mb-5">
                <ScoreGauge score={report.success_score.score} />
                <div className="text-center sm:text-left">
                  <p className="text-lg font-semibold text-text-primary">
                    {report.success_score.verdict || "サービス成功スコア"}
                  </p>
                  {report.success_score.key_factors.length > 0 && (
                    <ul className="mt-2 text-sm text-text-secondary space-y-1">
                      {report.success_score.key_factors.map((f, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="text-text-tertiary shrink-0">•</span>
                          <span className="prose prose-sm max-w-none"><Markdown remarkPlugins={[remarkGfm]}>{f}</Markdown></span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* Risk / Opportunity cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <RiskOpportunityCard type="risk" items={report.success_score.risks} />
                <RiskOpportunityCard type="opportunity" items={report.success_score.opportunities} />
              </div>
            </div>
          </section>
        )}

        {/* ─── Section: Executive Summary ─── */}
        {report?.executive_summary && (
          <section id="summary" className="scroll-mt-16">
            <div className="bg-interactive/5 rounded-lg border border-interactive/20 border-l-4 border-l-interactive p-6">
              <div className="prose prose-sm max-w-none text-text-secondary">
                <Markdown remarkPlugins={[remarkGfm]}>{report.executive_summary}</Markdown>
              </div>
            </div>
          </section>
        )}

        {/* ─── Section: Dimension Analysis (Radar + Table) ─── */}
        {prediction && prediction.dimension_predictions.length > 0 && (
          <section id="dimensions" className="scroll-mt-16">
            <div className="bg-surface-0 rounded-lg border border-border p-5">
              <h2 className="text-base font-semibold text-text-primary mb-1">
                シミュレーション {prediction.simulation_months}ヶ月間の指標推移
              </h2>
              <p className="text-xs text-text-tertiary mb-4">
                {prediction.simulation_months}ヶ月間のシミュレーションにおける各指標の初期値・最終値・変化傾向です
              </p>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Radar Chart */}
                <div>
                  <DimensionRadar predictions={prediction.dimension_predictions} />
                </div>

                {/* Prediction Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-text-tertiary">
                        <th className="py-2 pr-3 font-medium">指標</th>
                        <th className="py-2 px-3 font-medium text-center">開始時</th>
                        <th className="py-2 px-3 font-medium text-center">傾向</th>
                        <th className="py-2 pl-3 font-medium text-center">終了時</th>
                      </tr>
                    </thead>
                    <tbody className="text-text-primary">
                      {prediction.dimension_predictions.map((dp) => {
                        const inverted = isThreatDimension(dp.dimension);
                        // Start value: first round; End value: last round (current_value)
                        const startRaw = dp.trend.values.length > 0 ? dp.trend.values[0] : dp.current_value;
                        const startVal = inverted ? 1 - startRaw : startRaw;
                        const endVal = inverted ? 1 - dp.current_value : dp.current_value;
                        const rate = dp.trend.change_rate * (inverted ? -1 : 1);
                        const startLevel = startVal >= 0.6 ? "高" : startVal >= 0.3 ? "中" : "低";
                        const endLevel = endVal >= 0.6 ? "高" : endVal >= 0.3 ? "中" : "低";
                        const colorFor = (v: number) => v >= 0.6
                          ? "bg-positive-light text-positive" : v >= 0.3
                            ? "bg-caution-light text-caution" : "bg-negative-light text-negative";
                        const startColor = colorFor(startVal);
                        const endColor = colorFor(endVal);
                        const arrow = rate > 5 ? "↑" : rate < -5 ? "↓" : "→";
                        const arrowCls = rate > 5 ? "text-positive" : rate < -5 ? "text-negative" : "text-text-tertiary";

                        return (
                          <tr key={dp.dimension} className="border-b border-border last:border-b-0">
                            <td className="py-2.5 pr-3 font-medium text-xs">
                              {DIMENSION_LABELS[dp.dimension] || dp.dimension}
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <span className={`inline-block w-7 text-center text-xs font-bold rounded px-1 py-0.5 ${startColor}`}>{startLevel}</span>
                            </td>
                            <td className={`py-2.5 px-3 text-center text-sm font-medium ${arrowCls}`}>
                              {arrow}
                            </td>
                            <td className="py-2.5 pl-3 text-center">
                              <span className={`inline-block w-7 text-center text-xs font-bold rounded px-1 py-0.5 ${endColor}`}>{endLevel}</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ─── Section: Trend Sparklines ─── */}
        {prediction && prediction.dimension_predictions.length > 0 && (
          <section id="trends" className="scroll-mt-16">
            <h2 className="text-base font-semibold text-text-primary mb-3">
              指標トレンド
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {prediction.dimension_predictions.map((dp) => (
                <DimensionSparkline
                  key={dp.dimension}
                  dimension={dp.dimension}
                  values={dp.trend.values}
                  currentValue={dp.current_value}
                  changeRate={dp.trend.change_rate}
                />
              ))}
            </div>
          </section>
        )}

        {/* ─── Section: Prediction Highlights (timeline) ─── */}
        {prediction && prediction.highlights.length > 0 && (
          <section id="highlights" className="scroll-mt-16">
            <div className="bg-surface-0 rounded-lg border border-border p-6">
              <h2 className="text-base font-semibold text-text-primary mb-4">
                予測ハイライト
              </h2>
              <div className="relative pl-6">
                {/* Vertical timeline line */}
                <div className="absolute left-2 top-1 bottom-1 w-px bg-border-strong" />
                <ul className="space-y-4">
                  {prediction.highlights.map((h, i) => (
                    <li key={i} className="relative">
                      {/* Dot */}
                      <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full border-2 border-interactive bg-surface-0" />
                      <div className="text-sm text-text-secondary leading-relaxed prose prose-sm max-w-none">
                        <Markdown remarkPlugins={[remarkGfm]}>{h}</Markdown>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        )}

        {/* ─── Sections: Detail report sections (collapsible) ─── */}
        {report &&
          report.sections.length > 0 &&
          report.sections.map((section, i) => (
            <section
              key={i}
              id={`section-${i}`}
              className="scroll-mt-16"
            >
              <details
                className={`rounded-lg border border-border ${
                  i % 2 === 0 ? "bg-surface-0" : "bg-surface-2"
                } group`}
                open={i === 0}
              >
                <summary className="p-4 cursor-pointer select-none flex items-center gap-3 list-none [&::-webkit-details-marker]:hidden">
                  <span className="shrink-0 w-6 h-6 rounded-full bg-interactive/10 text-interactive text-xs font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <h2 className="text-base font-semibold text-text-primary flex-1">
                    {section.title}
                  </h2>
                  <svg
                    width="16" height="16" viewBox="0 0 16 16" fill="none"
                    className="shrink-0 text-text-tertiary transition-transform group-open:rotate-180"
                  >
                    <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </summary>
                <div className="px-4 pb-5 pt-0">
                  <div className="prose prose-sm max-w-none text-text-secondary ml-9">
                    {section.content ? (
                      <Markdown remarkPlugins={[remarkGfm]}>{section.content}</Markdown>
                    ) : (
                      <span className="text-text-tertiary">
                        内容がありません
                      </span>
                    )}
                  </div>
                </div>
              </details>
            </section>
          ))}

        {/* Metadata */}
        {report?.generated_at && (
          <p className="text-xs text-text-tertiary text-right pb-4">
            生成日時: {report.generated_at}
          </p>
        )}
      </main>
    </div>
  );
}
