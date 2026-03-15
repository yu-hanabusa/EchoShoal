/** APIクライアント — すべてのAPIはシミュレーション(job_id)スコープ */

import type {
  DocumentInfo,
  JobInfo,
  PredictionResult,
  ProcessResult,
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

/** シミュレーション一覧を取得 */
export async function listSimulations(): Promise<JobInfo[]> {
  return request("/simulations/");
}

/** このシミュレーション用の追加文書をアップロード */
export async function uploadSimulationDocument(
  jobId: string,
  file: File,
  source?: string,
): Promise<ProcessResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (source) {
    formData.append("source", source);
  }

  const res = await fetch(`${BASE_URL}/simulations/${jobId}/documents`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload error: ${res.status}`);
  }
  return res.json() as Promise<ProcessResult>;
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

/** シミュレーションを削除 */
export async function deleteSimulation(jobId: string): Promise<void> {
  await request(`/simulations/${jobId}`, { method: "DELETE" });
}

/** ヘルスチェック */
export async function healthCheck(): Promise<{ status: string; app: string }> {
  return request("/health");
}
