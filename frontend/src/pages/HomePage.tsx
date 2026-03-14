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
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold tracking-tight mb-4">
            Echo<span className="text-blue-400">Shoal</span>
          </h1>
          <p className="text-gray-400 text-lg">
            AI-powered IT Labor Market Prediction Simulator
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-300 text-center">
            {error}
          </div>
        )}

        <ScenarioForm
          onSubmit={(scenario) => mutation.mutate(scenario)}
          isLoading={mutation.isPending}
        />
      </div>
    </div>
  );
}
