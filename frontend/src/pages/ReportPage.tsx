import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getReport, getPrediction } from "../api/client";
import { SKILL_LABELS } from "../api/types";

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
              Claude APIを使用するため数十秒かかります
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

        {/* Hero: Executive Summary — the most important thing on this page */}
        {report?.executive_summary && (
          <div className="bg-surface-0 rounded-lg border border-border p-6">
            <h2 className="text-base font-semibold text-text-primary mb-3">
              エグゼクティブサマリー
            </h2>
            <p className="text-[15px] text-text-secondary leading-relaxed whitespace-pre-wrap">
              {report.executive_summary}
            </p>
          </div>
        )}

        {/* Prediction highlights — key takeaways */}
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

        {/* Comparison: Skill predictions table */}
        {prediction && prediction.skill_predictions.length > 0 && (
          <div className="bg-surface-0 rounded-lg border border-border p-5 overflow-x-auto">
            <h2 className="text-sm font-semibold text-text-primary mb-4">
              スキル別予測
            </h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-tertiary">
                  <th className="py-2 pr-3 font-medium">スキル</th>
                  <th className="py-2 px-3 font-medium text-right">
                    現在単価
                  </th>
                  <th className="py-2 px-3 font-medium text-right">
                    予測単価
                  </th>
                  <th className="py-2 px-3 font-medium text-right">
                    需要変化
                  </th>
                  <th className="py-2 pl-3 font-medium text-right">
                    不足人数
                  </th>
                </tr>
              </thead>
              <tbody className="text-text-primary">
                {prediction.skill_predictions.map((sp) => {
                  const rate = sp.demand_trend.change_rate;
                  const priceUp = sp.predicted_price > sp.current_price;
                  const priceDown = sp.predicted_price < sp.current_price;

                  return (
                    <tr
                      key={sp.skill}
                      className="border-b border-border last:border-b-0"
                    >
                      <td className="py-2.5 pr-3 font-medium">
                        {SKILL_LABELS[sp.skill] || sp.skill}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-text-secondary">
                        {sp.current_price > 0
                          ? `${sp.current_price.toFixed(0)}万`
                          : "—"}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right tabular-nums font-medium ${
                          priceUp
                            ? "text-positive"
                            : priceDown
                              ? "text-negative"
                              : "text-text-primary"
                        }`}
                      >
                        {sp.predicted_price > 0
                          ? `${sp.predicted_price.toFixed(0)}万`
                          : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
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
                      <td className="py-2.5 pl-3 text-right tabular-nums">
                        {sp.shortage_estimate > 0 ? (
                          <span className="text-negative">
                            {sp.shortage_estimate.toLocaleString()}人
                          </span>
                        ) : (
                          <span className="text-text-tertiary">—</span>
                        )}
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
              <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
                {section.content || (
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
