import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listBenchmarks, runFullBenchmark, runSingleBenchmark } from "../api/client";
import type { BenchmarkInfo } from "../api/types";

const TAG_COLORS: Record<string, string> = {
  success: "bg-positive-light text-positive",
  failure: "bg-negative-light text-negative",
  ai: "bg-purple-100 text-purple-700",
  saas: "bg-blue-100 text-blue-700",
  sns: "bg-pink-100 text-pink-700",
  streaming: "bg-orange-100 text-orange-700",
};

export default function BenchmarkListPage() {
  const navigate = useNavigate();
  const [launching, setLaunching] = useState<string | null>(null);

  const { data: benchmarks, isLoading, error } = useQuery({
    queryKey: ["benchmarks"],
    queryFn: listBenchmarks,
  });

  const handleRunFull = async (b: BenchmarkInfo) => {
    setLaunching(b.id);
    try {
      const res = await runFullBenchmark(b.id);
      navigate(`/benchmark/${res.job_id}`);
    } catch {
      setLaunching(null);
    }
  };

  const handleRunSimOnly = async (b: BenchmarkInfo) => {
    setLaunching(b.id);
    try {
      const res = await runSingleBenchmark(b.id);
      navigate(`/benchmark/${res.job_id}`);
    } catch {
      setLaunching(null);
    }
  };

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
        <p className="text-negative text-sm">{(error as Error).message}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Benchmark Scenarios</h1>
          <p className="text-sm text-text-tertiary mt-1">
            歴史的事例に基づくベンチマーク。市場調査→シミュレーション→評価の一連フローをテストします。
          </p>
        </div>

        <div className="grid gap-4">
          {benchmarks?.map((b) => (
            <div key={b.id} className="bg-surface-0 rounded-lg border border-border p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-text-primary">{b.name}</h3>
                  <p className="text-xs text-text-secondary mt-1">{b.description}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-text-tertiary">
                    <span>{b.num_rounds}ヶ月</span>
                    <span>{b.expected_trend_count}トレンド</span>
                    <div className="flex gap-1">
                      {b.tags.map((tag) => (
                        <span
                          key={tag}
                          className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${TAG_COLORS[tag] || "bg-surface-2 text-text-tertiary"}`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handleRunFull(b)}
                    disabled={launching === b.id}
                    className="px-3 py-1.5 rounded-md bg-interactive hover:bg-interactive-hover text-white text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {launching === b.id ? "..." : "調査+実行"}
                  </button>
                  <button
                    onClick={() => handleRunSimOnly(b)}
                    disabled={launching === b.id}
                    className="px-3 py-1.5 rounded-md border border-border hover:bg-surface-2 text-text-secondary text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    実行のみ
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
