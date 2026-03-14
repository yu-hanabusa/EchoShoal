import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import ScenarioForm from "../components/ScenarioForm";
import { createSimulation } from "../api/client";
import type { ScenarioInput } from "../api/types";

export default function HomePage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

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
      <header className="bg-surface-0 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <h1 className="text-lg font-semibold text-brand tracking-tight">
            EchoShoal
          </h1>
          <span className="text-text-tertiary text-sm">
            IT人材市場シミュレーター
          </span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {error && (
          <div
            className="mb-6 px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm"
            role="alert"
          >
            {error}
          </div>
        )}

        <ScenarioForm
          onSubmit={(scenario) => {
            setError(null);
            mutation.mutate(scenario);
          }}
          isLoading={mutation.isPending}
        />
      </main>
    </div>
  );
}
