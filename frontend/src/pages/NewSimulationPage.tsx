import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import ScenarioForm from "../components/ScenarioForm";
import DocumentUpload from "../components/DocumentUpload";
import { createSimulation, startSimulation } from "../api/client";
import type { ScenarioInput } from "../api/types";

export default function NewSimulationPage() {
  const navigate = useNavigate();
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadCount, setUploadCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Step 1: ジョブ作成
  const createMutation = useMutation({
    mutationFn: (scenario: ScenarioInput) => createSimulation(scenario),
    onSuccess: (data) => {
      setJobId(data.job_id);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Step 3: 実行開始
  const handleStart = async () => {
    if (!jobId) return;
    setStarting(true);
    setError(null);
    try {
      await startSimulation(jobId);
      navigate(`/simulation/${jobId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start simulation");
      setStarting(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-8">
        {error && (
          <div className="px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm" role="alert">
            {error}
          </div>
        )}

        {/* Phase 1: シナリオ入力 + ジョブ作成 */}
        {!jobId && (
          <>
            <div>
              <h2 className="text-lg font-semibold text-text-primary mb-2">New Simulation</h2>
              <p className="text-sm text-text-tertiary mb-6">
                シナリオとパラメータを設定してシミュレーションを作成します。
                作成後に参考資料をアップロードできます。
              </p>
            </div>
            <ScenarioForm
              onSubmit={(scenario) => {
                setError(null);
                createMutation.mutate(scenario);
              }}
              isLoading={createMutation.isPending}
              submitLabel="シミュレーションを作成"
            />
          </>
        )}

        {/* Phase 2: 文書アップロード + 実行開始 */}
        {jobId && (
          <>
            <div className="rounded-md border border-positive/30 bg-positive-light px-4 py-3">
              <p className="text-sm text-text-primary font-medium">
                シミュレーションを作成しました (ID: {jobId.slice(0, 8)}...)
              </p>
            </div>

            <fieldset className="rounded-md border border-border bg-surface-0 p-5">
              <legend className="px-2 text-sm font-medium text-text-secondary">
                参考資料のアップロード（任意）
              </legend>
              <p className="text-sm text-text-tertiary mb-4">
                IT業界レポートや求人データ等をアップロードすると、NLP解析で知識グラフにデータが蓄積され、シミュレーションの精度が向上します。
              </p>
              <DocumentUpload
                jobId={jobId}
                onUploaded={() => setUploadCount((c) => c + 1)}
              />
              {uploadCount > 0 && (
                <p className="mt-3 text-xs text-positive">
                  {uploadCount}件のドキュメントを投入済み
                </p>
              )}
            </fieldset>

            <button
              onClick={handleStart}
              disabled={starting}
              className="w-full py-3 px-6 rounded-md bg-interactive hover:bg-interactive-hover disabled:bg-border-strong disabled:text-text-tertiary text-white text-base font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed"
            >
              {starting ? "開始中..." : "シミュレーション開始"}
            </button>
          </>
        )}
      </main>
    </div>
  );
}
