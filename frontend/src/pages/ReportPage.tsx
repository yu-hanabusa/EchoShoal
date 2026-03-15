import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import { getReport, getPrediction } from "../api/client";
import { DIMENSION_LABELS } from "../api/types";

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

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
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
              レポートを生成中...
            </p>
            <p className="text-xs text-text-tertiary mt-1">
              LLMによる分析を行うため数十秒〜数分かかります。このページから離れないでください。
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

        {/* Success Score Card */}
        {report?.success_score && (
          <div className={`rounded-lg border p-6 ${
            report.success_score.score >= 70 ? "bg-positive/5 border-positive/30" :
            report.success_score.score >= 40 ? "bg-caution/5 border-caution/30" :
            "bg-negative/5 border-negative/30"
          }`}>
            <div className="flex items-center gap-4 mb-3">
              <span className={`text-5xl font-bold tabular-nums ${
                report.success_score.score >= 70 ? "text-positive" :
                report.success_score.score >= 40 ? "text-caution" :
                "text-negative"
              }`}>
                {report.success_score.score}
              </span>
              <div>
                <p className="text-base font-semibold text-text-primary">
                  {report.success_score.verdict || "サービス成功スコア"}
                </p>
                <p className="text-xs text-text-tertiary">/ 100</p>
              </div>
            </div>
            {report.success_score.key_factors.length > 0 && (
              <div className="mb-2">
                <p className="text-xs font-medium text-text-tertiary mb-1">判定根拠</p>
                <ul className="text-sm text-text-secondary space-y-0.5">
                  {report.success_score.key_factors.map((f, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-text-tertiary shrink-0">•</span>{f}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4 mt-3">
              {report.success_score.risks.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-negative mb-1">リスク</p>
                  <ul className="text-xs text-text-secondary space-y-0.5">
                    {report.success_score.risks.map((r, i) => <li key={i}>• {r}</li>)}
                  </ul>
                </div>
              )}
              {report.success_score.opportunities.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-positive mb-1">機会</p>
                  <ul className="text-xs text-text-secondary space-y-0.5">
                    {report.success_score.opportunities.map((o, i) => <li key={i}>• {o}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Hero: Executive Summary */}
        {report?.executive_summary && (
          <div className="bg-surface-0 rounded-lg border border-border p-6">
            <h2 className="text-base font-semibold text-text-primary mb-3">
              エグゼクティブサマリー
            </h2>
            <div className="prose prose-sm max-w-none text-text-secondary">
              <Markdown>{report.executive_summary}</Markdown>
            </div>
          </div>
        )}

        {/* Prediction highlights */}
        {prediction && prediction.highlights.length > 0 && (
          <div className="bg-surface-0 rounded-lg border border-border p-6">
            <h2 className="text-sm font-semibold text-text-primary mb-3">
              予測ハイライト
            </h2>
            <ul className="space-y-2">
              {prediction.highlights.map((h, i) => (
                <li
                  key={i}
                  className="text-sm text-text-secondary flex items-start gap-2 leading-relaxed"
                >
                  <span className="text-text-tertiary select-none shrink-0 mt-px">
                    •
                  </span>
                  <span>{h}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Dimension predictions table */}
        {prediction && prediction.dimension_predictions.length > 0 && (
          <div className="bg-surface-0 rounded-lg border border-border p-5 overflow-x-auto">
            <h2 className="text-sm font-semibold text-text-primary mb-4">
              ディメンション別予測
            </h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-tertiary">
                  <th className="py-2 pr-3 font-medium">ディメンション</th>
                  <th className="py-2 px-3 font-medium text-right">
                    現在値
                  </th>
                  <th className="py-2 px-3 font-medium text-right">
                    予測値
                  </th>
                  <th className="py-2 pl-3 font-medium text-right">
                    変化率
                  </th>
                </tr>
              </thead>
              <tbody className="text-text-primary">
                {prediction.dimension_predictions.map((dp) => {
                  const rate = dp.trend.change_rate;
                  const up = dp.predicted_value > dp.current_value;
                  const down = dp.predicted_value < dp.current_value;

                  return (
                    <tr
                      key={dp.dimension}
                      className="border-b border-border last:border-b-0"
                    >
                      <td className="py-2.5 pr-3 font-medium">
                        {DIMENSION_LABELS[dp.dimension] || dp.dimension}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-text-secondary">
                        {dp.current_value.toFixed(2)}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right tabular-nums font-medium ${
                          up
                            ? "text-positive"
                            : down
                              ? "text-negative"
                              : "text-text-primary"
                        }`}
                      >
                        {dp.predicted_value.toFixed(2)}
                      </td>
                      <td className="py-2.5 pl-3 text-right tabular-nums">
                        <span
                          className={
                            rate > 0
                              ? "text-positive"
                              : rate < 0
                                ? "text-negative"
                                : "text-text-tertiary"
                          }
                        >
                          {rate > 0 ? "+" : ""}
                          {rate.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Detail: report sections */}
        {report &&
          report.sections.length > 0 &&
          report.sections.map((section, i) => (
            <div
              key={i}
              className="bg-surface-0 rounded-lg border border-border p-6"
            >
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                {section.title}
              </h2>
              <div className="prose prose-sm max-w-none text-text-secondary">
                {section.content ? (
                  <Markdown>{section.content}</Markdown>
                ) : (
                  <span className="text-text-tertiary">
                    内容がありません
                  </span>
                )}
              </div>
            </div>
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
