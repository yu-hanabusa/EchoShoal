import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimulation, getSimulationDocuments } from "../api/client";
import ActionTimeline from "../components/ActionTimeline";
import ProgressBar from "../components/ProgressBar";
import MarketChart from "../components/MarketChart";
import AgentTable from "../components/AgentTable";
import type { DocumentInfo } from "../api/types";

type Tab = "results" | "documents";

export default function SimulationPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("results");

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

        {/* Completed: Tabs */}
        {isCompleted && result && (
          <>
            {/* Tab Bar */}
            <div className="flex gap-1 border-b border-border">
              {(["results", "documents"] as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? "border-interactive text-interactive"
                      : "border-transparent text-text-tertiary hover:text-text-secondary"
                  }`}
                >
                  {tab === "results" ? "結果" : "投入資料"}
                </button>
              ))}
            </div>

            {/* Results Tab */}
            {activeTab === "results" && (
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

            {/* Documents Tab */}
            {activeTab === "documents" && <DocumentsTab jobId={jobId!} />}
          </>
        )}
      </main>
    </div>
  );
}

function DocumentsTab({ jobId }: { jobId: string }) {
  const { data: docs, isLoading } = useQuery({
    queryKey: ["sim-documents", jobId],
    queryFn: () => getSimulationDocuments(jobId),
  });

  if (isLoading) return <p className="text-sm text-text-tertiary py-6 text-center">Loading...</p>;
  if (!docs || docs.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface-0 p-8 text-center">
        <p className="text-text-tertiary text-sm">このシミュレーションに投入された資料はありません。</p>
        <p className="text-text-tertiary text-xs mt-1">新規作成時にファイルを添付すると、NLPでエンティティを抽出しシミュレーションの参考情報にします。</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border bg-surface-0 p-5 overflow-x-auto">
        <h3 className="text-sm font-medium text-text-primary mb-3">投入資料一覧</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-text-tertiary">
              <th className="py-2 pr-3 font-medium">ファイル名</th>
              <th className="py-2 px-3 font-medium">ソース</th>
              <th className="py-2 px-3 font-medium text-right">文字数</th>
              <th className="py-2 pl-3 font-medium text-right">抽出エンティティ数</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc: DocumentInfo) => (
              <tr key={doc.doc_id} className="border-b border-border last:border-b-0">
                <td className="py-2.5 pr-3 font-medium">{doc.filename}</td>
                <td className="py-2.5 px-3 text-text-secondary">{doc.source || "\u2014"}</td>
                <td className="py-2.5 px-3 text-right tabular-nums">
                  {doc.text_length > 1000 ? `${(doc.text_length / 1000).toFixed(1)}K` : doc.text_length}
                </td>
                <td className="py-2.5 pl-3 text-right tabular-nums">{doc.entity_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rounded-md border border-border bg-surface-1 p-4">
        <p className="text-xs text-text-tertiary">
          投入資料がシミュレーション結果にどう影響したかの詳細分析は、
          <span className="font-medium text-interactive">「View Report」</span>
          の「資料影響分析」セクションで確認できます。
        </p>
      </div>
    </div>
  );
}

