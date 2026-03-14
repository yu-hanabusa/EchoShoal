/** APIクライアント */

import type {
  JobInfo,
  PredictionResult,
  ScenarioInput,
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

/** シミュレーションジョブを作成 */
export async function createSimulation(
  scenario: ScenarioInput
): Promise<{ job_id: string; status: string }> {
  return request("/simulations/", {
    method: "POST",
    body: JSON.stringify(scenario),
  });
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

/** ヘルスチェック */
export async function healthCheck(): Promise<{ status: string; app: string }> {
  return request("/health");
}
