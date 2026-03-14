import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";

const BASE_URL = "/api";

export default function NewSimulationPage() {
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const [numRounds, setNumRounds] = useState(24);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const charCount = description.length;
  const isValid = charCount >= 10;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    setSubmitting(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("description", description);
      formData.append("num_rounds", String(numRounds));
      for (const file of files) {
        formData.append("files", file);
      }

      const res = await fetch(`${BASE_URL}/simulations/`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Error: ${res.status}`);
      }

      const data = await res.json();
      navigate(`/simulation/${data.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create simulation");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-lg font-semibold text-text-primary mb-6">New Simulation</h1>

        {error && (
          <div className="mb-6 px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Scenario */}
          <div>
            <label htmlFor="scenario" className="block text-base font-medium text-text-primary mb-1">
              Scenario
            </label>
            <p className="text-sm text-text-tertiary mb-3">
              Describe the market scenario you want to simulate. AI acceleration, economic impact, and policy changes will be automatically detected from your text.
            </p>
            <textarea
              id="scenario"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              required
              minLength={10}
              maxLength={2000}
              placeholder="Example: AI技術の急速な普及により、SES企業のエンジニア需要が変化する。大手SIerはAI導入支援に舵を切り、中小SES企業はレガシー保守案件の減少に直面する..."
              className="w-full rounded-md bg-surface-0 border border-border px-4 py-3 text-text-primary placeholder-text-tertiary text-[15px] leading-relaxed focus:border-interactive focus:ring-1 focus:ring-interactive outline-none resize-y min-h-[120px]"
            />
            <div className="mt-1.5 flex justify-end">
              <span className={`text-xs tabular-nums ${charCount > 0 && charCount < 10 ? "text-caution" : "text-text-tertiary"}`}>
                {charCount > 0 && `${charCount} / 2000`}
              </span>
            </div>
          </div>

          {/* Documents */}
          <fieldset className="rounded-md border border-border bg-surface-0 p-5">
            <legend className="px-2 text-sm font-medium text-text-secondary">
              Seed Documents (optional)
            </legend>
            <p className="text-sm text-text-tertiary mb-3">
              Upload industry reports, job data, or news articles. NLP will extract entities to build the simulation's knowledge graph.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.pdf,text/plain,application/pdf"
              multiple
              onChange={handleFileChange}
              className="block w-full text-sm text-text-primary file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-surface-2 file:text-text-secondary hover:file:bg-border file:cursor-pointer file:transition-colors"
            />
            {files.length > 0 && (
              <ul className="mt-3 space-y-1">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between text-sm text-text-secondary bg-surface-1 rounded px-3 py-1.5">
                    <span className="truncate">{f.name} ({(f.size / 1024).toFixed(0)}KB)</span>
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      className="text-negative hover:text-negative/70 ml-2 text-xs"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>

          {/* Simulation Period */}
          <div className="flex items-baseline gap-3">
            <label htmlFor="rounds" className="text-sm text-text-secondary">
              Simulation Period
            </label>
            <input
              id="rounds"
              type="number"
              value={numRounds}
              onChange={(e) => setNumRounds(Number(e.target.value))}
              min={1}
              max={36}
              className="w-20 rounded-md bg-surface-0 border border-border px-3 py-1.5 text-sm text-text-primary focus:border-interactive focus:ring-1 focus:ring-interactive outline-none tabular-nums"
            />
            <span className="text-sm text-text-tertiary">months</span>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting || !isValid}
            className="w-full py-3 px-6 rounded-md bg-interactive hover:bg-interactive-hover disabled:bg-border-strong disabled:text-text-tertiary text-white text-base font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {submitting ? "Starting..." : "Start Simulation"}
          </button>
        </form>
      </main>
    </div>
  );
}
