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
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-4 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-2xl font-bold tracking-tight">
            Echo<span className="text-blue-400">Shoal</span>
          </Link>
          <Link
            to={`/simulation/${jobId}`}
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            結果に戻る
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {isLoading && (
          <p className="text-center text-gray-400 py-12">
            レポートを生成中...（Claude APIを使用するため数十秒かかります）
          </p>
        )}

        {error && (
          <div className="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-300 text-center">
            {(error as Error).message}
          </div>
        )}

        {prediction && prediction.highlights.length > 0 && (
          <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-6">
            <h2 className="text-lg font-bold text-blue-300 mb-3">
              予測ハイライト
            </h2>
            <ul className="space-y-2">
              {prediction.highlights.map((h, i) => (
                <li key={i} className="text-gray-200 flex items-start gap-2">
                  <span className="text-blue-400 mt-0.5">-</span>
                  {h}
                </li>
              ))}
            </ul>
          </div>
        )}

        {prediction && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-6 overflow-x-auto">
            <h2 className="text-lg font-bold text-gray-200 mb-4">
              スキル別予測
            </h2>
            <table className="w-full text-sm text-gray-300">
              <thead>
                <tr className="border-b border-gray-700 text-left">
                  <th className="py-2 px-3">スキル</th>
                  <th className="py-2 px-3 text-right">現在単価</th>
                  <th className="py-2 px-3 text-right">予測単価</th>
                  <th className="py-2 px-3 text-right">需要変化</th>
                  <th className="py-2 px-3 text-right">不足人数</th>
                </tr>
              </thead>
              <tbody>
                {prediction.skill_predictions.map((sp) => (
                  <tr key={sp.skill} className="border-b border-gray-800">
                    <td className="py-2 px-3 font-medium text-gray-100">
                      {SKILL_LABELS[sp.skill] || sp.skill}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {sp.current_price.toFixed(0)}万円
                    </td>
                    <td className="py-2 px-3 text-right">
                      {sp.predicted_price.toFixed(0)}万円
                    </td>
                    <td className="py-2 px-3 text-right">
                      <span className={sp.demand_trend.change_rate > 0 ? "text-green-400" : sp.demand_trend.change_rate < 0 ? "text-red-400" : "text-gray-400"}>
                        {sp.demand_trend.change_rate > 0 ? "+" : ""}{sp.demand_trend.change_rate.toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right">
                      {sp.shortage_estimate > 0 ? (
                        <span className="text-red-400">{sp.shortage_estimate.toLocaleString()}人</span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {report && (
          <div className="space-y-6">
            {report.executive_summary && (
              <div className="bg-gray-900 rounded-lg border border-gray-800 p-6">
                <h2 className="text-lg font-bold text-gray-200 mb-3">
                  エグゼクティブサマリー
                </h2>
                <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                  {report.executive_summary}
                </p>
              </div>
            )}

            {report.sections.map((section, i) => (
              <div key={i} className="bg-gray-900 rounded-lg border border-gray-800 p-6">
                <h2 className="text-lg font-bold text-gray-200 mb-3">
                  {section.title}
                </h2>
                <div className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                  {section.content}
                </div>
              </div>
            ))}

            <p className="text-gray-500 text-sm text-center">
              生成日時: {report.generated_at}
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
