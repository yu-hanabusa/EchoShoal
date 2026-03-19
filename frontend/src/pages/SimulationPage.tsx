import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimulation, getReport, getSimulationDocuments, getDocumentDetail } from "../api/client";
import type { DocumentInfo } from "../api/types";
import RelationshipGraph from "../components/RelationshipGraph";
import ProgressBar from "../components/ProgressBar";
import MarketChart from "../components/MarketChart";

const DOC_LABELS: Record<string, string> = {
  "market_report.txt": "市場レポート",
  "user_behavior.txt": "ユーザー行動分析",
  "stakeholders.txt": "ステークホルダー分析",
  "github_readme.md": "GitHub README",
};

function DocItem({ doc, jobId }: { doc: DocumentInfo; jobId: string }) {
  const [open, setOpen] = useState(false);
  const { data: detail } = useQuery({
    queryKey: ["document-detail", jobId, doc.doc_id],
    queryFn: () => getDocumentDetail(jobId, doc.doc_id),
    enabled: open,
  });
  const label = DOC_LABELS[doc.filename] || doc.filename;

  return (
    <div className="border-b border-border last:border-b-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full py-2 text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="transition-transform text-text-tertiary text-[10px]" style={{ display: "inline-block", transform: open ? "rotate(90deg)" : "none" }}>▸</span>
          <span className="text-xs text-text-secondary truncate">{label}</span>
          <span className="text-[10px] text-text-tertiary shrink-0">
            {(doc.text_length / 1000).toFixed(1)}K文字
          </span>
        </div>
      </button>
      {open && (
        <div className="pb-3 pl-4">
          {detail?.text_summary ? (
            <>
              <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                {detail.text_summary}
              </p>
              <a
                href={`/api/simulations/${jobId}/documents/${doc.doc_id}/download`}
                download
                className="inline-flex items-center gap-1 mt-2 text-[10px] text-interactive hover:text-interactive-hover"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3" /></svg>
                全文をダウンロード
              </a>
            </>
          ) : (
            <p className="text-[10px] text-text-tertiary">読み込み中...</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function SimulationPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [chartsOpen, setChartsOpen] = useState(false);

  const { data, error, isLoading } = useQuery({
    queryKey: ["simulation", jobId],
    queryFn: () => getSimulation(jobId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
    enabled: !!jobId,
  });

  const isCompleted = data?.status === "completed";

  // レポートからスコアを取得（完了時のみ）
  const { data: report } = useQuery({
    queryKey: ["report", jobId],
    queryFn: () => getReport(jobId!),
    enabled: !!jobId && isCompleted,
    retry: false,
  });

  // ドキュメント一覧を取得（完了時のみ）
  const { data: documents } = useQuery({
    queryKey: ["documents", jobId],
    queryFn: () => getSimulationDocuments(jobId!),
    enabled: !!jobId && isCompleted,
    retry: false,
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
  const result = data.result;
  const scenario = result?.scenario;
  const successScore = report?.success_score;

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* ナビゲーション */}
        <div className="flex items-center justify-between">
          <Link to="/" className="text-sm text-text-tertiary hover:text-interactive">
            &larr; Simulations
          </Link>
          {isCompleted && (
            <Link
              to={`/simulation/${jobId}/report`}
              className="px-4 py-1.5 rounded-md bg-interactive hover:bg-interactive-hover text-white text-sm font-medium transition-colors"
            >
              レポートを見る
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
            シミュレーション失敗
            {data.error && <span className="block mt-1 text-text-secondary">{data.error}</span>}
          </div>
        )}

        {/* Completed: Results */}
        {isCompleted && result && (
          <div className="space-y-6">
            {/* サービス情報ヘッダー */}
            <div className="bg-surface-0 rounded-lg border border-border p-6">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-text-primary truncate">
                  {scenario?.service_name || "シミュレーション結果"}
                </h1>
                {scenario?.service_url && (
                  <a
                    href={scenario.service_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-tertiary hover:text-interactive shrink-0"
                    title={scenario.service_url}
                  >
                    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z" /></svg>
                  </a>
                )}
              </div>
              {scenario?.description && (
                <p className="text-sm text-text-secondary mt-1 leading-relaxed">{scenario.description}</p>
              )}
              <div className="flex items-center gap-3 mt-2">
                {scenario?.target_market && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-tertiary">
                    対象市場: {scenario.target_market}
                  </span>
                )}
                <span className="text-[10px] text-text-tertiary">
                  {result.summary.total_rounds}ヶ月間 / {result.summary.agents.length}ステークホルダー
                </span>
              </div>

              {/* 成功スコア */}
              {successScore && (() => {
                const pct = Math.min(Math.max(successScore.score, 0), 100);
                const barColor = pct >= 60
                  ? "bg-positive"
                  : pct >= 30
                    ? "bg-caution"
                    : "bg-negative";
                const textColor = pct >= 60
                  ? "text-positive"
                  : pct >= 30
                    ? "text-caution"
                    : "text-negative";
                return (
                  <div className="mt-4 pt-3 border-t border-border">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-medium text-text-secondary shrink-0 w-20">成功可能性</span>
                      <div className="flex-1 bg-surface-2 rounded-full h-2.5">
                        <div
                          className={`h-2.5 rounded-full transition-all ${barColor}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className={`text-sm font-bold shrink-0 tabular-nums ${textColor}`}>
                        {successScore.score}<span className="text-text-tertiary font-normal text-xs"> / 100</span>
                      </span>
                    </div>
                    <p className={`text-xs mt-1 ml-[92px] ${textColor}`}>{successScore.verdict}</p>
                  </div>
                );
              })()}
            </div>

            {/* シミュレーション概要 + 推移チャート */}
            <div className="bg-surface-0 rounded-lg border border-border p-6">
              <h2 className="text-sm font-semibold text-text-primary mb-1">シミュレーション概要</h2>
              <p className="text-xs text-text-tertiary mb-3">
                LLMがシナリオとエージェント行動を分析した定性的評価です。
              </p>
              <div className="space-y-2">
                {[
                  { key: "user_adoption", label: "市場浸透",
                    high: "ターゲット市場に広く受け入れられる見込みです",
                    mid: "一定の浸透は見込めますが、拡大には課題があります",
                    low: "市場への浸透は限定的と予測されます" },
                  { key: "competitive_pressure", label: "競合優位性", invert: true,
                    high: "競合の脅威は低く、有利なポジションです",
                    mid: "一定の競合はありますが、対処可能な水準です",
                    low: "競合の脅威が高く、差別化戦略が不可欠です" },
                  { key: "revenue_potential", label: "収益性",
                    high: "持続的な収益を生む可能性が高いと評価されます",
                    mid: "収益化は可能ですが、成長には追加の施策が必要です",
                    low: "現状のモデルでは収益化に課題があります" },
                  { key: "ecosystem_health", label: "エコシステム",
                    high: "連携サービスやコミュニティが活発で成長基盤があります",
                    mid: "エコシステムは発展途上です",
                    low: "エコシステムが未成熟で、単独での成長が求められます" },
                ].map(({ key, label, high, mid, low, invert }) => {
                  const raw = result.summary.final_market.dimensions?.[key] ?? 0;
                  const val = invert ? 1 - raw : raw;
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

              {/* 推移チャート（アコーディオン） */}
              <div className="mt-4 pt-3 border-t border-border">
                <button
                  onClick={() => setChartsOpen(!chartsOpen)}
                  className="flex items-center gap-1.5 text-xs font-medium text-text-tertiary hover:text-text-secondary w-full text-left py-1"
                >
                  <span className="transition-transform" style={{ display: "inline-block", transform: chartsOpen ? "rotate(90deg)" : "none" }}>▸</span>
                  推移チャート
                </button>
                {chartsOpen && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-2">
                    <MarketChart rounds={result.rounds} title="サービスの成長指標の変化" dimensions={["user_adoption", "revenue_potential", "market_awareness", "ecosystem_health"]} />
                    <MarketChart rounds={result.rounds} title="サービスを取り巻くリスクの変化" dimensions={["competitive_pressure", "regulatory_risk", "tech_maturity", "funding_climate"]} />
                  </div>
                )}
              </div>
            </div>

            {/* ステークホルダー関係図 + 議論 */}
            <RelationshipGraph
              rounds={result.rounds}
              agents={result.summary.agents}
              serviceName={result.scenario?.service_name}
              initialRelationships={result.summary.initial_relationships}
              socialFeed={result.social_feed}
            />

            {/* 使用データ */}
            {documents && documents.length > 0 && (
              <div className="bg-surface-0 rounded-lg border border-border p-5">
                <h3 className="text-sm font-medium text-text-primary mb-2">使用データ</h3>
                <p className="text-[10px] text-text-tertiary mb-2">
                  シミュレーションで参照した市場調査データの要約です。クリックで内容を確認できます。
                </p>
                <div>
                  {documents.map((doc) => (
                    <DocItem key={doc.doc_id} doc={doc} jobId={jobId!} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
