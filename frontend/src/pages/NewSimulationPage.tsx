import { useState, useRef, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { startMarketResearch, getMarketResearch, getSimulation } from "../api/client";
import type { MarketResearchResult } from "../api/types";

const BASE_URL = "/api";

const GITHUB_URL_PATTERN = /^https?:\/\/github\.com\/[^/]+\/[^/]+\/?$/;
const ALLOWED_FILE_EXTENSIONS = [".txt", ".md", ".csv"];
const MAX_FILE_SIZE_MB = 5;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const MAX_FILES = 10;

const LIMITS = {
  serviceName: 100,
  serviceDescription: 500,
  scenario: { min: 10, max: 2000 },
  numRounds: { min: 1, max: 36 },
  targetYear: { min: 2000, max: new Date().getFullYear() },
} as const;

function isValidGithubUrl(url: string): boolean {
  if (!url) return true;
  return GITHUB_URL_PATTERN.test(url.trim());
}

function getFileExtension(name: string): string {
  const idx = name.lastIndexOf(".");
  return idx >= 0 ? name.slice(idx).toLowerCase() : "";
}

export default function NewSimulationPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const resumeJobId = searchParams.get("resume");

  const [jobId, setJobId] = useState<string | null>(resumeJobId);
  const [serviceName, setServiceName] = useState("");
  const [serviceDescription, setServiceDescription] = useState("");
  const [serviceUrl, setServiceUrl] = useState("");
  const [description, setDescription] = useState("");
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());
  const [numRounds, setNumRounds] = useState(12);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [researching, setResearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [researchResult, setResearchResult] = useState<MarketResearchResult | null>(null);
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [restored, setRestored] = useState(!resumeJobId);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // resume: 既存ジョブからフォーム状態を復元
  const { data: resumeData } = useQuery({
    queryKey: ["simulation", resumeJobId],
    queryFn: () => getSimulation(resumeJobId!),
    enabled: !!resumeJobId && !restored,
  });

  useEffect(() => {
    if (!resumeData?.scenario || restored) return;
    const s = resumeData.scenario;
    setServiceName(s.service_name || "");
    setServiceDescription(s.service_description || "");
    setServiceUrl(s.service_url || "");
    setDescription(s.description || "");
    if (s.target_year) setTargetYear(s.target_year);
    if (s.num_rounds) setNumRounds(s.num_rounds);
    setRestored(true);
  }, [resumeData, restored]);

  // resume: 市場調査結果もあれば復元
  const { data: researchResumeData } = useQuery({
    queryKey: ["research-resume", resumeJobId],
    queryFn: () => getMarketResearch(resumeJobId!),
    enabled: !!resumeJobId && restored && !researchResult && !researching,
  });

  useEffect(() => {
    if (!researchResumeData) return;
    if (researchResumeData.status === "completed" && researchResumeData.result) {
      setResearchResult(researchResumeData.result);
    } else if (researchResumeData.status === "researching") {
      setResearching(true);
    }
  }, [researchResumeData]);

  // 市場調査ポーリング
  const { data: pollingData } = useQuery({
    queryKey: ["research-poll", jobId],
    queryFn: () => getMarketResearch(jobId!),
    enabled: !!jobId && researching,
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (!pollingData) return;
    if (pollingData.status === "completed" && pollingData.result) {
      setResearchResult(pollingData.result);
      setResearching(false);
    } else if (pollingData.status === "failed") {
      setError(pollingData.error || "市場調査に失敗しました");
      setResearching(false);
    }
  }, [pollingData]);

  const charCount = description.length;
  const isValid = charCount >= LIMITS.scenario.min && !urlError;
  const canResearch = serviceName.trim().length > 0 && !researching;

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
    setFileError(null);

    const newFiles = Array.from(selected);
    const totalCount = files.length + newFiles.length;
    if (totalCount > MAX_FILES) {
      setFileError(`ファイルは最大${MAX_FILES}件までです（現在${files.length}件選択済み）`);
      e.target.value = "";
      return;
    }

    const invalidExt = newFiles.filter(
      (f) => !ALLOWED_FILE_EXTENSIONS.includes(getFileExtension(f.name)),
    );
    if (invalidExt.length > 0) {
      setFileError(
        `対応ファイル形式: ${ALLOWED_FILE_EXTENSIONS.join(", ")}（${invalidExt.map((f) => f.name).join(", ")} は非対応）`,
      );
      e.target.value = "";
      return;
    }

    const tooLarge = newFiles.filter((f) => f.size > MAX_FILE_SIZE_BYTES);
    if (tooLarge.length > 0) {
      setFileError(
        `ファイルサイズは${MAX_FILE_SIZE_MB}MB以下にしてください（${tooLarge.map((f) => f.name).join(", ")}）`,
      );
      e.target.value = "";
      return;
    }

    setFiles((prev) => [...prev, ...newFiles]);
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setFileError(null);
  };

  const handleResearch = async () => {
    if (!canResearch) return;
    setError(null);
    try {
      const resp = await startMarketResearch({
        serviceName,
        serviceDescription,
        description: description || undefined,
        serviceUrl: serviceUrl || undefined,
        targetYear,
        jobId: jobId || undefined,
      });
      setJobId(resp.job_id);
      setResearching(true);
      // URL にジョブIDを反映（ページリロードで復元可能にする）
      window.history.replaceState(null, "", `/new?resume=${resp.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "市場調査の開始に失敗しました");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    if (serviceUrl && !isValidGithubUrl(serviceUrl)) {
      setUrlError("https://github.com/owner/repo の形式で入力してください");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const fullDescription = serviceDescription
        ? `【サービス概要】${serviceDescription}\n\n${description}`
        : description;

      const formData = new FormData();
      formData.append("description", fullDescription);
      formData.append("num_rounds", String(numRounds));
      formData.append("service_name", serviceName);
      formData.append("target_year", String(targetYear));
      if (serviceUrl) formData.append("service_url", serviceUrl);
      if (jobId) formData.append("job_id", jobId);
      for (const file of files) {
        formData.append("files", file);
      }

      const res = await fetch(`${BASE_URL}/simulations/`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `エラー: ${res.status}`);
      }

      const data = await res.json();
      navigate(`/simulation/${data.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "シミュレーションの作成に失敗しました");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleReport = (key: string) => {
    setExpandedReport(expandedReport === key ? null : key);
  };

  return (
    <div className="min-h-screen bg-surface-1">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-lg font-semibold text-text-primary mb-6">新規シミュレーション</h1>

        {error && (
          <div className="mb-6 px-4 py-3 rounded-md bg-negative-light border border-negative/20 text-negative text-sm" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* サービス情報 */}
          <fieldset className="rounded-md border border-border bg-surface-0 p-5 space-y-4">
            <legend className="px-2 text-base font-medium text-text-primary">
              サービス情報
            </legend>

            <div>
              <label htmlFor="serviceName" className="block text-sm font-medium text-text-secondary mb-1">
                サービス名
              </label>
              <input
                id="serviceName"
                type="text"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value.slice(0, LIMITS.serviceName))}
                maxLength={LIMITS.serviceName}
                placeholder="例: TeamChat、CodeAssist"
                className="w-full rounded-md bg-surface-1 border border-border px-4 py-2.5 text-text-primary placeholder-text-tertiary text-[15px] focus:border-interactive focus:ring-1 focus:ring-interactive outline-none"
              />
              <div className="mt-1 flex justify-end">
                <span className={`text-xs tabular-nums ${serviceName.length >= LIMITS.serviceName ? "text-caution" : "text-text-tertiary"}`}>
                  {serviceName.length > 0 && `${serviceName.length} / ${LIMITS.serviceName}`}
                </span>
              </div>
            </div>

            <div>
              <label htmlFor="serviceDescription" className="block text-sm font-medium text-text-secondary mb-1">
                サービス概要
              </label>
              <p className="text-xs text-text-tertiary mb-2">
                どのようなサービスですか？ 誰向けですか？ どんな課題を解決しますか？
              </p>
              <textarea
                id="serviceDescription"
                value={serviceDescription}
                onChange={(e) => setServiceDescription(e.target.value.slice(0, LIMITS.serviceDescription))}
                maxLength={LIMITS.serviceDescription}
                rows={3}
                placeholder="例: 日本の中小企業向けビジネスチャットツール。Slackライクな機能を日本語UIと国内データセンターで提供し、セキュリティ重視の企業をターゲットにする。"
                className="w-full rounded-md bg-surface-1 border border-border px-4 py-2.5 text-text-primary placeholder-text-tertiary text-[15px] leading-relaxed focus:border-interactive focus:ring-1 focus:ring-interactive outline-none resize-y min-h-[80px]"
              />
              <div className="mt-1 flex justify-end">
                <span className={`text-xs tabular-nums ${serviceDescription.length >= LIMITS.serviceDescription ? "text-caution" : "text-text-tertiary"}`}>
                  {serviceDescription.length > 0 && `${serviceDescription.length} / ${LIMITS.serviceDescription}`}
                </span>
              </div>
            </div>

            <div>
              <label htmlFor="serviceUrl" className="block text-sm font-medium text-text-secondary mb-1">
                GitHub URL（任意）
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

            {/* 対象年 */}
            <div className="flex items-baseline gap-3">
              <label htmlFor="targetYear" className="text-sm font-medium text-text-secondary">
                対象年
              </label>
              <input
                id="targetYear"
                type="number"
                value={targetYear}
                onChange={(e) => setTargetYear(Number(e.target.value))}
                min={LIMITS.targetYear.min}
                max={LIMITS.targetYear.max}
                className="w-24 rounded-md bg-surface-1 border border-border px-3 py-1.5 text-sm text-text-primary focus:border-interactive focus:ring-1 focus:ring-interactive outline-none tabular-nums"
              />
              <span className="text-xs text-text-tertiary">市場調査で取得するデータの年</span>
            </div>
          </fieldset>

          {/* 市場調査 */}
          <fieldset className="rounded-md border border-border bg-surface-0 p-5 space-y-4">
            <legend className="px-2 text-base font-medium text-text-primary">
              市場調査
            </legend>
            <p className="text-sm text-text-tertiary">
              Google Trends・GitHub・Yahoo Finance からデータを収集し、市場分析レポートを自動生成します。
            </p>

            <button
              type="button"
              onClick={handleResearch}
              disabled={!canResearch || researching}
              className="px-5 py-2.5 rounded-md bg-interactive hover:bg-interactive-hover disabled:bg-border-strong disabled:text-text-tertiary text-white text-sm font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed"
            >
              {researching ? "市場調査を実行中..." : researchResult ? "市場調査を再実行" : "市場調査を実行"}
            </button>

            {/* 調査中インジケータ */}
            {researching && (
              <div className="flex items-center gap-2 text-sm text-text-secondary">
                <div className="w-4 h-4 border-2 border-interactive border-t-transparent rounded-full animate-spin" />
                バックグラウンドで市場調査を実行中です。ページを離れても処理は継続します。
              </div>
            )}

            {/* 調査結果 */}
            {researchResult && (
              <div className="space-y-3 mt-4">
                {/* データソース状況 */}
                <div className="rounded-md border border-border bg-surface-1 p-4 space-y-2">
                  <p className="text-xs font-medium text-text-secondary mb-2">データソース状況</p>
                  {(() => {
                    const sources = researchResult.collected_data.sources_used;
                    const trends = researchResult.collected_data.trends;
                    const github = researchResult.collected_data.github_repos;
                    const finance = researchResult.collected_data.finance_data;
                    const errors = researchResult.collected_data.errors;
                    const allSources = ["Google Trends", "GitHub API", "Yahoo Finance"];
                    const hasLlmFallback = sources.length < allSources.length;

                    return (
                      <>
                        {allSources.map((name) => {
                          const ok = sources.includes(name);
                          const err = errors.find((e) => e.toLowerCase().includes(name.toLowerCase().split(" ")[0].toLowerCase()));
                          let detail = "";
                          if (name === "Google Trends" && ok) {
                            const points = trends.reduce((sum, t) => sum + Object.keys(t.interest_over_time).length, 0);
                            detail = `${trends.length}キーワード・${points}データポイント取得済み`;
                          } else if (name === "GitHub API" && ok) {
                            detail = `リポジトリ${github.length}件取得済み`;
                          } else if (name === "Yahoo Finance" && ok) {
                            detail = `企業${finance.length}件取得済み`;
                          } else if (err) {
                            detail = "取得失敗";
                          } else if (!ok) {
                            detail = "データなし";
                          }

                          return (
                            <div key={name} className="flex items-center gap-2 text-xs">
                              <span className={ok ? "text-positive" : "text-text-tertiary"}>
                                {ok ? "\u2705" : "\u274c"}
                              </span>
                              <span className={`font-medium ${ok ? "text-text-primary" : "text-text-tertiary"}`}>
                                {name}
                              </span>
                              <span className="text-text-tertiary">— {detail}</span>
                            </div>
                          );
                        })}
                        {hasLlmFallback && (
                          <div className="flex items-center gap-2 text-xs mt-1 pt-1 border-t border-border">
                            <span className="text-interactive">&#x2139;&#xFE0F;</span>
                            <span className="text-text-secondary">
                              取得できなかったデータはLLMが業界知識で補完しています
                            </span>
                          </div>
                        )}
                        {sources.length === allSources.length && (
                          <div className="flex items-center gap-2 text-xs mt-1 pt-1 border-t border-border">
                            <span className="text-positive">&#x2705;</span>
                            <span className="text-text-secondary">
                              全データソースから取得完了。実データに基づくレポートです
                            </span>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>

                {/* レポート折りたたみ */}
                {[
                  { key: "market", label: "市場分析レポート", content: researchResult.market_report },
                  { key: "user", label: "ユーザー行動レポート", content: researchResult.user_behavior },
                  { key: "stakeholder", label: "ステークホルダーレポート", content: researchResult.stakeholders },
                ].map(({ key, label, content }) => (
                  <div key={key} className="border border-border rounded-md">
                    <button
                      type="button"
                      onClick={() => toggleReport(key)}
                      className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-text-primary hover:bg-surface-1 transition-colors cursor-pointer"
                    >
                      <span>{label}</span>
                      <span className="text-text-tertiary">{expandedReport === key ? "▲" : "▼"}</span>
                    </button>
                    {expandedReport === key && (
                      <div className="px-4 pb-4 text-sm text-text-secondary whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
                        {content || "（生成に失敗しました）"}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </fieldset>

          {/* シナリオ */}
          <div>
            <label htmlFor="scenario" className="block text-base font-medium text-text-primary mb-1">
              シナリオ
            </label>
            <p className="text-sm text-text-tertiary mb-3">
              市場の状況、競合環境、シミュレーションの前提条件を記述してください。経済・技術パラメータは自動検出されます。
            </p>
            <textarea
              id="scenario"
              value={description}
              onChange={(e) => setDescription(e.target.value.slice(0, LIMITS.scenario.max))}
              rows={5}
              required
              minLength={LIMITS.scenario.min}
              maxLength={LIMITS.scenario.max}
              placeholder="例: 2026年4月に正式リリース。月額500円〜のフリーミアムモデルで参入。Microsoft Teams（シェア17.25%）が圧倒的に強い市場で、AI議事録機能とオンプレミス版を差別化要因にセキュリティ重視の製造業・金融をターゲットにする"
              className="w-full rounded-md bg-surface-0 border border-border px-4 py-3 text-text-primary placeholder-text-tertiary text-[15px] leading-relaxed focus:border-interactive focus:ring-1 focus:ring-interactive outline-none resize-y min-h-[120px]"
            />
            <div className="mt-1.5 flex justify-between">
              <span className={`text-xs ${charCount > 0 && charCount < LIMITS.scenario.min ? "text-caution" : "text-text-tertiary"}`}>
                {charCount > 0 && charCount < LIMITS.scenario.min && `あと${LIMITS.scenario.min - charCount}文字以上入力してください`}
              </span>
              <span className={`text-xs tabular-nums ${charCount > 0 && charCount < LIMITS.scenario.min ? "text-caution" : "text-text-tertiary"}`}>
                {charCount > 0 && `${charCount} / ${LIMITS.scenario.max}`}
              </span>
            </div>
          </div>

          {/* シード文書 */}
          <fieldset className="rounded-md border border-border bg-surface-0 p-5">
            <legend className="px-2 text-sm font-medium text-text-secondary">
              シード文書（任意）
            </legend>
            <p className="text-sm text-text-tertiary mb-3">
              市場レポート、競合分析、サービス資料などをアップロードできます（{ALLOWED_FILE_EXTENSIONS.join(", ")} 形式、最大{MAX_FILE_SIZE_MB}MB/件、{MAX_FILES}件まで）
            </p>
            <label className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-surface-2 text-sm font-medium text-text-secondary hover:bg-border transition-colors cursor-pointer">
              <span>ファイルを選択</span>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ALLOWED_FILE_EXTENSIONS.join(",")}
                onChange={handleFileChange}
                className="sr-only"
              />
            </label>
            <span className="ml-3 text-xs text-text-tertiary">
              {files.length > 0 ? `${files.length}件選択済み` : "未選択（複数回追加可能）"}
            </span>
            {fileError && (
              <p className="mt-2 text-xs text-negative">{fileError}</p>
            )}
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
                      削除
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>

          {/* シミュレーション期間 */}
          <div className="flex items-baseline gap-3">
            <label htmlFor="rounds" className="text-sm text-text-secondary">
              シミュレーション期間
            </label>
            <input
              id="rounds"
              type="number"
              value={numRounds}
              onChange={(e) => setNumRounds(Math.min(Math.max(Number(e.target.value), LIMITS.numRounds.min), LIMITS.numRounds.max))}
              min={LIMITS.numRounds.min}
              max={LIMITS.numRounds.max}
              className="w-20 rounded-md bg-surface-0 border border-border px-3 py-1.5 text-sm text-text-primary focus:border-interactive focus:ring-1 focus:ring-interactive outline-none tabular-nums"
            />
            <span className="text-sm text-text-tertiary">ヶ月（1〜36）</span>
          </div>

          {/* 送信 */}
          <button
            type="submit"
            disabled={submitting || !isValid || researching}
            className="w-full py-3 px-6 rounded-md bg-interactive hover:bg-interactive-hover disabled:bg-border-strong disabled:text-text-tertiary text-white text-base font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {submitting ? "シミュレーションを開始中..." : "シミュレーションを開始"}
          </button>
        </form>
      </main>
    </div>
  );
}
