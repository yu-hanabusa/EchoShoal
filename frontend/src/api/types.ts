/** バックエンドAPI の型定義 */

export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  created_at: string;
  progress: {
    current_round?: number;
    total_rounds?: number;
    percentage?: number;
  };
  error?: string | null;
  result?: SimulationResult;
}

export interface ScenarioInput {
  description: string;
  num_rounds?: number;
  focus_industries?: string[];
  focus_skills?: string[];
  ai_acceleration?: number;
  economic_shock?: number;
  policy_change?: string | null;
}

export interface MarketState {
  round_number: number;
  skill_demand: Record<string, number>;
  skill_supply: Record<string, number>;
  unit_prices: Record<string, number>;
  unemployment_rate: number;
  ai_automation_rate: number;
  remote_work_rate: number;
  overseas_outsource_rate: number;
}

export interface RoundResult {
  round_number: number;
  market_state: MarketState;
  actions_taken: Array<{
    agent: string;
    type: string;
    description: string;
  }>;
  events: string[];
}

export interface AgentSummary {
  id: string;
  name: string;
  type: string;
  industry: string;
  headcount: number;
  revenue: number;
  satisfaction: number;
  reputation: number;
}

export interface SimulationResult {
  scenario: ScenarioInput;
  summary: {
    total_rounds: number;
    final_market: MarketState;
    agents: AgentSummary[];
    llm_calls: number;
  };
  rounds: RoundResult[];
}

export interface TrendData {
  values: number[];
  slope: number;
  start_value: number;
  end_value: number;
  change_rate: number;
  moving_avg: number[];
}

export interface SkillPrediction {
  skill: string;
  current_demand: number;
  predicted_demand: number;
  demand_trend: TrendData;
  current_price: number;
  predicted_price: number;
  price_trend: TrendData;
  shortage_estimate: number;
}

export interface PredictionResult {
  simulation_months: number;
  total_engineers: number;
  skill_predictions: SkillPrediction[];
  macro_predictions: Record<string, TrendData>;
  highlights: string[];
}

export interface ReportSection {
  title: string;
  content: string;
  data?: Record<string, unknown> | null;
}

export interface SimulationReport {
  title: string;
  scenario_description: string;
  executive_summary: string;
  sections: ReportSection[];
  generated_at: string;
}

/** 文書処理結果 */
export interface ProcessResult {
  document_id: string;
  filename: string;
  entities_found: number;
  technologies: string[];
  organizations: string[];
  policies: string[];
  keywords: string[];
  new_nodes_created: number;
}

/** 文書情報 */
export interface DocumentInfo {
  doc_id: string;
  filename: string;
  source: string;
  text_length: number;
  entity_count: number;
  uploaded_at: string;
}

/** スキルカテゴリの日本語ラベル */
export const SKILL_LABELS: Record<string, string> = {
  legacy: "レガシー",
  web_frontend: "Webフロントエンド",
  web_backend: "Webバックエンド",
  cloud_infra: "クラウド・インフラ",
  ai_ml: "AI・機械学習",
  security: "セキュリティ",
  mobile: "モバイル",
  erp: "ERP",
};

/** スキルカテゴリの表示色 */
export const SKILL_COLORS: Record<string, string> = {
  legacy: "#9ca3af",
  web_frontend: "#60a5fa",
  web_backend: "#34d399",
  cloud_infra: "#f97316",
  ai_ml: "#a78bfa",
  security: "#ef4444",
  mobile: "#fbbf24",
  erp: "#06b6d4",
};
