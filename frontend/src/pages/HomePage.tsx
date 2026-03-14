import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSimulations, deleteSimulation } from "../api/client";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  created: { label: "作成済み", color: "text-text-tertiary" },
  queued: { label: "待機中", color: "text-caution" },
  running: { label: "実行中", color: "text-interactive" },
  completed: { label: "完了", color: "text-positive" },
  failed: { label: "失敗", color: "text-negative" },
};

export default function HomePage() {
  const queryClient = useQueryClient();
  const { data: simulations, isLoading } = useQuery({
    queryKey: ["simulations"],
    queryFn: listSimulations,
    refetchInterval: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => deleteSimulation(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["simulations"] }),
  });

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
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-tertiary">
                  <th className="py-3 px-4 font-medium">シナリオ</th>
                  <th className="py-3 px-4 font-medium w-24">状態</th>
                  <th className="py-3 px-4 font-medium w-36 text-right">作成日時</th>
                </tr>
              </thead>
              <tbody>
                {simulations.map((sim) => {
                  const status = STATUS_LABELS[sim.status] || STATUS_LABELS.created;
                  return (
                    <tr
                      key={sim.job_id}
                      className="border-b border-border last:border-b-0 hover:bg-surface-1 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <Link
                          to={
                            sim.status === "created"
                              ? `/new?resume=${sim.job_id}`
                              : `/simulation/${sim.job_id}`
                          }
                          className="text-text-primary hover:text-interactive font-medium"
                        >
                          {sim.scenario_description || "(no description)"}
                        </Link>
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
          </div>
        )}
      </main>
    </div>
  );
}
