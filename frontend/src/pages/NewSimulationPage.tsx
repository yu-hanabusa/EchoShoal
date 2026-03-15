import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";

const BASE_URL = "/api";

const GITHUB_URL_PATTERN = /^https?:\/\/github\.com\/[^/]+\/[^/]+\/?$/;

function isValidGithubUrl(url: string): boolean {
  if (!url) return true; // 空は許可（任意フィールド）
  return GITHUB_URL_PATTERN.test(url.trim());
}

export default function NewSimulationPage() {
  const navigate = useNavigate();
  const [serviceName, setServiceName] = useState("");
  const [serviceDescription, setServiceDescription] = useState("");
  const [serviceUrl, setServiceUrl] = useState("");
  const [description, setDescription] = useState("");
  const [numRounds, setNumRounds] = useState(24);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const charCount = description.length;
  const isValid = charCount >= 10 && !urlError;

  const handleUrlChange = (value: string) => {
    setServiceUrl(value);
    if (value && !isValidGithubUrl(value)) {
      setUrlError("https://github.com/owner/repo の形式で入力してください");
    } else {
      setUrlError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected || selected.length === 0) return;
    const newFiles = Array.from(selected);
    setFiles((prev) => [...prev, ...newFiles]);
    // 同じファイルを再選択できるようにリセット
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    // GitHub URL最終チェック
    if (serviceUrl && !isValidGithubUrl(serviceUrl)) {
      setUrlError("https://github.com/owner/repo の形式で入力してください");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // シナリオにサービス概要を先頭に含める
      const fullDescription = serviceDescription
        ? `【サービス概要】${serviceDescription}\n\n${description}`
        : description;

      const formData = new FormData();
      formData.append("description", fullDescription);
      formData.append("num_rounds", String(numRounds));
      formData.append("service_name", serviceName);
      if (serviceUrl) formData.append("service_url", serviceUrl);
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
    } finally {
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

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Service Info */}
          <fieldset className="rounded-md border border-border bg-surface-0 p-5 space-y-4">
            <legend className="px-2 text-base font-medium text-text-primary">
              Service Information
            </legend>

            <div>
              <label htmlFor="serviceName" className="block text-sm font-medium text-text-secondary mb-1">
                Service Name
              </label>
              <input
                id="serviceName"
                type="text"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="Example: TeamChat, CodeAssist..."
                className="w-full rounded-md bg-surface-1 border border-border px-4 py-2.5 text-text-primary placeholder-text-tertiary text-[15px] focus:border-interactive focus:ring-1 focus:ring-interactive outline-none"
              />
            </div>

            <div>
              <label htmlFor="serviceDescription" className="block text-sm font-medium text-text-secondary mb-1">
                Service Overview
              </label>
              <p className="text-xs text-text-tertiary mb-2">
                What does this service do? Who is it for? What problem does it solve?
              </p>
              <textarea
                id="serviceDescription"
                value={serviceDescription}
                onChange={(e) => setServiceDescription(e.target.value)}
                rows={3}
                placeholder="Example: 日本の中小企業向けビジネスチャットツール。Slackライクな機能を日本語UIと国内データセンターで提供し、セキュリティ重視の企業をターゲットにする。"
                className="w-full rounded-md bg-surface-1 border border-border px-4 py-2.5 text-text-primary placeholder-text-tertiary text-[15px] leading-relaxed focus:border-interactive focus:ring-1 focus:ring-interactive outline-none resize-y min-h-[80px]"
              />
            </div>

            <div>
              <label htmlFor="serviceUrl" className="block text-sm font-medium text-text-secondary mb-1">
                GitHub URL (optional)
              </label>
              <p className="text-xs text-text-tertiary mb-2">
                READMEを自動取得してシミュレーションの参考情報にします
              </p>
              <input
                id="serviceUrl"
                type="url"
                value={serviceUrl}
                onChange={(e) => handleUrlChange(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className={`w-full rounded-md bg-surface-1 border px-4 py-2.5 text-text-primary placeholder-text-tertiary text-[15px] focus:ring-1 outline-none ${
                  urlError
                    ? "border-negative focus:border-negative focus:ring-negative"
                    : "border-border focus:border-interactive focus:ring-interactive"
                }`}
              />
              {urlError && (
                <p className="mt-1 text-xs text-negative">{urlError}</p>
              )}
            </div>
          </fieldset>

          {/* Scenario */}
          <div>
            <label htmlFor="scenario" className="block text-base font-medium text-text-primary mb-1">
              Scenario
            </label>
            <p className="text-sm text-text-tertiary mb-3">
              Describe the market context, competitive landscape, and conditions for the simulation. Economic and technology parameters will be automatically detected.
            </p>
            <textarea
              id="scenario"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              required
              minLength={10}
              maxLength={2000}
              placeholder="Example: 2026年4月に正式リリース。月額500円〜のフリーミアムモデルで参入。Microsoft Teams（シェア17.25%）が圧倒的に強い市場で、AI議事録機能とオンプレミス版を差別化要因にセキュリティ重視の製造業・金融をターゲットにする..."
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
              Upload market reports, competitor analysis, or service documentation (.txt files).
            </p>
            <label className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-surface-2 text-sm font-medium text-text-secondary hover:bg-border transition-colors cursor-pointer">
              <span>ファイルを選択</span>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileChange}
                className="sr-only"
              />
            </label>
            <span className="ml-3 text-xs text-text-tertiary">
              {files.length > 0 ? `${files.length}件選択済み` : "未選択（複数回追加可能）"}
            </span>
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
