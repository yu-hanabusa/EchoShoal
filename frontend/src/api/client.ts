/** APIクライアント — すべてのAPIはシミュレーション(job_id)スコープ */

import type {
  BenchmarkInfo,
  DocumentDetail,
  DocumentInfo,
  EvaluationJobResult,
  JobInfo,
  MarketResearchResult,
  PaginatedResponse,
  PredictionResult,
  SimulationReport,
} from "./types";

const BASE_URL = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** 市場調査を実行 */
export async function runMarketResearch(
  serviceName: string,
  description: string,
  targetYear: number,
): Promise<MarketResearchResult> {
  const formData = new FormData();
  formData.append("service_name", serviceName);
  formData.append("description", description);
  formData.append("target_year", String(targetYear));

  const res = await fetch(`${BASE_URL}/simulations/research`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Research error: ${res.status}`);
  }
  return res.json() as Promise<MarketResearchResult>;
}

/** シミュレーション一覧を取得（ページネーション対応） */
export async function listSimulations(
  skip = 0,
  limit = 20,
): Promise<PaginatedResponse<JobInfo>> {
  return request(`/simulations/?skip=${skip}&limit=${limit}`);
}

/** ジョブのステータス + 結果を取得 */
export async function getSimulation(jobId: string): Promise<JobInfo> {
  return request(`/simulations/${jobId}`);
}

/** シミュレーション進捗を取得 */
export async function getProgress(
  jobId: string
): Promise<{ job_id: string; status: string; progress: Record<string, number> }> {
  return request(`/simulations/${jobId}/progress`);
}

/** レポートを取得 */
export async function getReport(jobId: string): Promise<SimulationReport> {
  return request(`/simulations/${jobId}/report`);
}

/** 予測結果を取得 */
export async function getPrediction(jobId: string): Promise<PredictionResult> {
  return request(`/simulations/${jobId}/prediction`);
}

/** このシミュレーションの文書一覧を取得 */
export async function getSimulationDocuments(jobId: string): Promise<DocumentInfo[]> {
  return request(`/simulations/${jobId}/documents`);
}

/** 文書の詳細（要約テキスト含む）を取得 */
export async function getDocumentDetail(jobId: string, docId: string): Promise<DocumentDetail> {
  return request(`/simulations/${jobId}/documents/${docId}`);
}

/** このシミュレーションの知識グラフ可視化データを取得 */
export async function getSimulationGraph(jobId: string): Promise<{
  elements: Array<{ data: Record<string, string> }>;
}> {
  return request(`/simulations/${jobId}/graph`);
}

/** 2つのシミュレーションを比較 */
export async function compareSimulations(
  baseJobId: string,
  altJobId: string,
): Promise<Record<string, unknown>> {
  return request(`/simulations/${baseJobId}/compare/${altJobId}`);
}

/** シナリオ名を更新 */
export async function updateSimulation(
  jobId: string,
  body: { scenario_name: string },
): Promise<void> {
  await request(`/simulations/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** シミュレーションを削除 */
export async function deleteSimulation(jobId: string): Promise<void> {
  await request(`/simulations/${jobId}`, { method: "DELETE" });
}

/** ベンチマーク一覧を取得 */
export async function listBenchmarks(): Promise<BenchmarkInfo[]> {
  return request("/evaluation/benchmarks");
}

/** 一連ベンチマーク（市場調査+シミュレーション+評価）を実行 */
export async function runFullBenchmark(
  benchmarkId: string,
): Promise<{ job_id: string; status: string; benchmark_id: string; benchmark_name: string }> {
  return request(`/evaluation/run/${benchmarkId}/full`, { method: "POST" });
}

/** 単一ベンチマークを実行 */
export async function runSingleBenchmark(
  benchmarkId: string,
): Promise<{ job_id: string; status: string; benchmark_id: string; benchmark_name: string }> {
  return request(`/evaluation/run/${benchmarkId}`, { method: "POST" });
}

/** 評価ジョブの結果を取得 */
export async function getEvaluationResult(jobId: string): Promise<EvaluationJobResult> {
  return request(`/evaluation/${jobId}/result`);
}

/** ヘルスチェック */
export async function healthCheck(): Promise<{ status: string; app: string }> {
  return request("/health");
}
