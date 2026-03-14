import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSimulation, getSimulationDocuments, getSimulationGraph } from "../api/client";
import ActionTimeline from "../components/ActionTimeline";
import ProgressBar from "../components/ProgressBar";
import MarketChart from "../components/MarketChart";
import AgentTable from "../components/AgentTable";
import type { DocumentInfo } from "../api/types";

type Tab = "results" | "documents" | "graph";

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
              {(["results", "documents", "graph"] as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? "border-interactive text-interactive"
                      : "border-transparent text-text-tertiary hover:text-text-secondary"
                  }`}
                >
                  {tab === "results" ? "結果" : tab === "documents" ? "投入資料" : "知識グラフ"}
                </button>
              ))}
            </div>

            {/* Results Tab */}
            {activeTab === "results" && (
              <div className="space-y-6">
                <div className="bg-surface-0 rounded-lg border border-border p-6">
                  <div className="flex flex-col md:flex-row md:items-end gap-6">
                    <div className="flex-1">
                      <p className="text-sm text-text-tertiary mb-1">最終失業率</p>
                      <p className="text-4xl font-bold text-text-primary tabular-nums tracking-tight">
                        {(result.summary.final_market.unemployment_rate * 100).toFixed(1)}
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
                  <MarketChart rounds={result.rounds} dataKey="skill_demand" title="スキル需要の推移" skills={["ai_ml", "cloud_infra", "web_backend", "legacy"]} />
                  <MarketChart rounds={result.rounds} dataKey="unit_prices" title="単価の推移（万円/月）" skills={["ai_ml", "cloud_infra", "web_backend", "legacy"]} />
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

            {/* Graph Tab */}
            {activeTab === "graph" && <GraphTab jobId={jobId!} />}
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
        <p className="text-text-tertiary text-sm">No documents uploaded for this simulation.</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface-0 p-5 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-text-tertiary">
            <th className="py-2 pr-3 font-medium">Filename</th>
            <th className="py-2 px-3 font-medium">Source</th>
            <th className="py-2 px-3 font-medium text-right">Size</th>
            <th className="py-2 pl-3 font-medium text-right">Entities</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc: DocumentInfo) => (
            <tr key={doc.doc_id} className="border-b border-border last:border-b-0">
              <td className="py-2.5 pr-3 font-medium">{doc.filename}</td>
              <td className="py-2.5 px-3 text-text-secondary">{doc.source || "\u2014"}</td>
              <td className="py-2.5 px-3 text-right tabular-nums">
                {doc.text_length > 1000 ? `${(doc.text_length / 1000).toFixed(1)}K` : doc.text_length} chars
              </td>
              <td className="py-2.5 pl-3 text-right tabular-nums">{doc.entity_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GraphTab({ jobId }: { jobId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["sim-graph", jobId],
    queryFn: () => getSimulationGraph(jobId),
  });

  if (isLoading) return <p className="text-sm text-text-tertiary py-6 text-center">Loading graph...</p>;
  if (!data?.elements?.length) {
    return (
      <div className="rounded-md border border-border bg-surface-0 p-8 text-center">
        <p className="text-text-tertiary text-sm">No knowledge graph data for this simulation.</p>
      </div>
    );
  }

  const NODE_COLORS: Record<string, string> = {
    Agent: "#3b82f6", Skill: "#10b981", Document: "#8b5cf6",
    Company: "#f97316", Policy: "#ef4444", StatRecord: "#9ca3af",
  };

  const nodes: Array<{ id: string; label: string; type: string; x: number; y: number }> = [];
  const edges: Array<{ source: string; target: string }> = [];

  for (const el of data.elements) {
    if (el.data.source && el.data.target) {
      edges.push({ source: el.data.source, target: el.data.target });
    } else if (el.data.id) {
      nodes.push({ id: el.data.id, label: el.data.label || el.data.id, type: el.data.type || "Unknown", x: 0, y: 0 });
    }
  }

  // Layout by type
  const byType: Record<string, typeof nodes> = {};
  for (const n of nodes) {
    if (!byType[n.type]) byType[n.type] = [];
    byType[n.type].push(n);
  }
  const width = 900;
  let y = 50;
  for (const group of Object.values(byType)) {
    const spacing = Math.min(100, (width - 80) / Math.max(group.length, 1));
    const startX = (width - spacing * (group.length - 1)) / 2;
    group.forEach((n, i) => { n.x = startX + i * spacing; n.y = y + (Math.random() * 15 - 7); });
    y += 90;
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  return (
    <div>
      <div className="flex gap-3 mb-3 flex-wrap">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1 text-xs text-text-secondary">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
            {type}
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-border overflow-hidden bg-surface-0">
        <svg width="100%" viewBox={`0 0 ${width} ${Math.max(y + 30, 300)}`}>
          {edges.map((e, i) => {
            const s = nodeMap.get(e.source);
            const t = nodeMap.get(e.target);
            if (!s || !t) return null;
            return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="#d1d5db" strokeWidth={1} opacity={0.5} />;
          })}
          {nodes.map((n) => (
            <g key={n.id}>
              <circle cx={n.x} cy={n.y} r={8} fill={NODE_COLORS[n.type] || "#9ca3af"} opacity={0.85} />
              <text x={n.x} y={n.y + 20} textAnchor="middle" fontSize={8} fill="#6b7280">
                {n.label.length > 10 ? n.label.slice(0, 10) + ".." : n.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <p className="text-xs text-text-tertiary mt-1">{nodes.length} nodes, {edges.length} edges</p>
    </div>
  );
}
