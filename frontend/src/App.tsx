import { useState, useEffect } from "react";

type HealthResponse = {
  status: string;
  app: string;
};

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then(setHealth)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center">
      <div className="text-center space-y-6">
        <h1 className="text-5xl font-bold tracking-tight">
          Echo<span className="text-blue-400">Shoal</span>
        </h1>
        <p className="text-gray-400 text-lg">
          AI-powered IT Labor Market Prediction Simulator
        </p>
        <div className="mt-8 p-4 rounded-lg bg-gray-900 border border-gray-800">
          {health ? (
            <p className="text-green-400">
              Backend: {health.status} ({health.app})
            </p>
          ) : error ? (
            <p className="text-red-400">Backend: {error}</p>
          ) : (
            <p className="text-yellow-400">Connecting to backend...</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
