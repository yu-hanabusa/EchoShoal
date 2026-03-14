import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import ScenarioForm from "../components/ScenarioForm";
import DocumentUpload from "../components/DocumentUpload";
import { createSimulation } from "../api/client";
import type { ScenarioInput } from "../api/types";

export default function HomePage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [uploadCount, setUploadCount] = useState(0);

  const mutation = useMutation({
    mutationFn: (scenario: ScenarioInput) => createSimulation(scenario),
    onSuccess: (data) => {
      navigate(`/simulation/${data.job_id}`);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-8">
        {error && (
          <div
            className="px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm"
            role="alert"
          >
            {error}
          </div>
        )}

        {/* Step 1: Document Upload (optional) */}
        <fieldset className="rounded-md border border-border bg-surface-0 p-5">
          <legend className="px-2 text-sm font-medium text-text-secondary">
            Step 1: 参考資料のアップロード（任意）
          </legend>
          <p className="text-sm text-text-tertiary mb-4">
            IT業界レポートや求人データ等をアップロードすると、NLP解析で知識グラフにデータが蓄積され、シミュレーションの精度が向上します。
          </p>
          <DocumentUpload onUploaded={() => setUploadCount((c) => c + 1)} />
          {uploadCount > 0 && (
            <p className="mt-3 text-xs text-positive">
              {uploadCount}件のドキュメントを知識グラフに投入済み
            </p>
          )}
        </fieldset>

        {/* Step 2: Scenario + Parameters + Submit */}
        <div>
          <p className="text-sm font-medium text-text-secondary mb-4 px-2">
            Step 2: シナリオ & パラメータ設定
          </p>
          <ScenarioForm
            onSubmit={(scenario) => {
              setError(null);
              mutation.mutate(scenario);
            }}
            isLoading={mutation.isPending}
          />
        </div>
      </main>
    </div>
  );
}
