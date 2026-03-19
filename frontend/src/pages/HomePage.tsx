import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSimulations, deleteSimulation, updateSimulation } from "../api/client";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  created: { label: "作成済み", color: "text-text-tertiary" },
  queued: { label: "待機中", color: "text-caution" },
  running: { label: "実行中", color: "text-interactive" },
  completed: { label: "完了", color: "text-positive" },
  failed: { label: "失敗", color: "text-negative" },
};

const PAGE_SIZE = 20;

export default function HomePage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["simulations", page],
    queryFn: () => listSimulations(page * PAGE_SIZE, PAGE_SIZE),
    refetchInterval: false,
  });

  const simulations = data?.items;
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => deleteSimulation(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulations"] });
      // 最終ページの最後のアイテムを削除した場合、前のページに戻る
      if (page > 0 && simulations && simulations.length <= 1) {
        setPage((p) => p - 1);
      }
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ jobId, name }: { jobId: string; name: string }) =>
      updateSimulation(jobId, { scenario_name: name }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["simulations"] }),
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEditing = (jobId: string, currentName: string) => {
    setEditingId(jobId);
    setEditValue(currentName);
  };

  const commitRename = (jobId: string) => {
    const trimmed = editValue.trim();
    if (trimmed) {
      renameMutation.mutate({ jobId, name: trimmed });
    }
    setEditingId(null);
  };

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-text-primary">
            Simulations
          </h1>
          <Link
            to="/new"
            className="px-5 py-2 rounded-md bg-interactive hover:bg-interactive-hover text-white text-sm font-medium transition-colors"
          >
            + New Simulation
          </Link>
        </div>

        {isLoading ? (
          <p className="text-sm text-text-tertiary text-center py-12">
            Loading...
          </p>
        ) : !simulations || simulations.length === 0 ? (
          <div className="rounded-md border border-border bg-surface-0 p-12 text-center">
            <p className="text-text-secondary mb-4">
              まだシミュレーションがありません
            </p>
            <Link
              to="/new"
              className="text-interactive hover:underline text-sm font-medium"
            >
              最初のシミュレーションを作成する
            </Link>
          </div>
        ) : (
          <div className="rounded-md border border-border bg-surface-0 overflow-hidden">
            <table className="w-full text-sm table-fixed">
              <thead>
                <tr className="border-b border-border text-left text-text-tertiary">
                  <th className="py-3 px-4 font-medium">シナリオ</th>
                  <th className="py-3 px-4 font-medium w-24">状態</th>
                  <th className="py-3 px-4 font-medium w-36 text-right">作成日時</th>
                  <th className="py-3 px-4 font-medium w-16"></th>
                </tr>
              </thead>
              <tbody>
                {simulations.map((sim) => {
                  const status = STATUS_LABELS[sim.status] || STATUS_LABELS.created;
                  const displayName = sim.scenario_name || sim.service_name || sim.scenario_description || "(no description)";
                  const isEditing = editingId === sim.job_id;
                  return (
                    <tr
                      key={sim.job_id}
                      className="border-b border-border last:border-b-0 hover:bg-surface-1 transition-colors"
                    >
                      <td className="py-3 px-4 min-w-0">
                        {isEditing ? (
                          <input
                            autoFocus
                            className="w-full px-2 py-1 text-sm border border-interactive rounded bg-surface-0 text-text-primary outline-none"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onBlur={() => commitRename(sim.job_id)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitRename(sim.job_id);
                              if (e.key === "Escape") setEditingId(null);
                            }}
                          />
                        ) : (
                          <div className="flex items-center gap-2 min-w-0">
                            <Link
                              to={
                                sim.status === "created"
                                  ? `/new?resume=${sim.job_id}`
                                  : `/simulation/${sim.job_id}`
                              }
                              className="text-text-primary hover:text-interactive font-medium truncate"
                              title={sim.scenario_description || ""}
                            >
                              {displayName}
                            </Link>
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                startEditing(sim.job_id, displayName);
                              }}
                              className="shrink-0 text-text-tertiary hover:text-interactive transition-colors"
                              title="シナリオ名を編集"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </button>
                          </div>
                        )}
                      </td>
                      <td className={`py-3 px-4 font-medium ${status.color}`}>
                        {status.label}
                      </td>
                      <td className="py-3 px-4 text-right text-text-tertiary text-xs tabular-nums">
                        {new Date(sim.created_at).toLocaleString("ja-JP", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            if (confirm("このシミュレーションを削除しますか？")) {
                              deleteMutation.mutate(sim.job_id);
                            }
                          }}
                          className="text-xs text-text-tertiary hover:text-negative transition-colors"
                        >
                          削除
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* ページネーション */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-border px-4 py-3">
                <span className="text-xs text-text-tertiary">
                  {total}件中 {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)}件
                </span>
                <div className="flex items-center gap-2">
                  <button
                    disabled={page === 0}
                    onClick={() => setPage((p) => p - 1)}
                    className="px-3 py-1 text-xs rounded border border-border text-text-secondary hover:bg-surface-1 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    前へ
                  </button>
                  <span className="text-xs text-text-secondary tabular-nums">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage((p) => p + 1)}
                    className="px-3 py-1 text-xs rounded border border-border text-text-secondary hover:bg-surface-1 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    次へ
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
