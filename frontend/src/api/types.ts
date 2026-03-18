/** バックエンドAPI の型定義 */

export type JobStatus = "created" | "queued" | "running" | "completed" | "failed";

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  created_at: string;
  scenario_description?: string;
  service_name?: string;
  scenario_name?: string;
  progress: {
    current_round?: number;
    total_rounds?: number;
    percentage?: number;
    phase?: string;
  };
  error?: string | null;
  result?: SimulationResult;
}

export interface ScenarioInput {
  description: string;
  num_rounds?: number;
  service_name?: string;
  service_url?: string | null;
  target_market?: string | null;
  regulatory_change?: string | null;
}

export interface ServiceMarketState {
  round_number: number;
  service_name: string;
  dimensions: Record<string, number>;
  economic_sentiment: number;
  tech_hype_level: number;
  regulatory_pressure: number;
  remote_work_adoption: number;
  ai_disruption_level: number;
}

export type ActionVisibility = "public" | "private" | "partial";

export interface ActionTaken {
  agent: string;
  type: string;
  description: string;
  visibility: ActionVisibility;
  reacting_to?: string;
}

export interface RoundResult {
  round_number: number;
  market_state: ServiceMarketState;
  actions_taken: ActionTaken[];
  events: string[];
  summary?: string;
}

export interface AgentPersonality {
  conservatism: number;
  bandwagon: number;
  overconfidence: number;
  sunk_cost_bias: number;
  info_sensitivity: number;
  noise: number;
  description: string;
}

export interface AgentSummary {
  id: string;
  name: string;
  type: string;
  stakeholder_type: string;
  description?: string;
  headcount: number;
  revenue: number;
  satisfaction: number;
  reputation: number;
  personality?: AgentPersonality;
}

export interface Relationship {
  from: string;
  to: string;
  type: string;
  round: number;
  weight: number;
}

export interface SimulationResult {
  scenario: ScenarioInput;
  summary: {
    total_rounds: number;
    final_market: ServiceMarketState;
    agents: AgentSummary[];
    llm_calls: number;
    engine?: string;
    oasis_stats?: OasisStats;
    initial_relationships?: Relationship[];
  };
  rounds: RoundResult[];
  social_feed?: SocialPost[];
}

export interface TrendData {
  values: number[];
  slope: number;
  start_value: number;
  end_value: number;
  change_rate: number;
  moving_avg: number[];
}

export interface DimensionPrediction {
  dimension: string;
  current_value: number;
  predicted_value: number;
  trend: TrendData;
}

export interface PredictionResult {
  simulation_months: number;
  dimension_predictions: DimensionPrediction[];
  macro_predictions: Record<string, TrendData>;
  highlights: string[];
}

export interface SuccessScore {
  score: number;
  verdict: string;
  key_factors: string[];
  risks: string[];
  opportunities: string[];
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
  success_score?: SuccessScore | null;
  generated_at: string;
}

/** OASIS SNSフィード */
export interface SocialPost {
  id: string;
  type: "post";
  author: string;
  content: string;
  created_at: string;
  round?: number | null;
  likes: number;
  dislikes: number;
  shares: number;
  comments: SocialComment[];
}

export interface SocialComment {
  author: string;
  content: string;
  created_at: string;
  likes: number;
}

/** OASIS統計 */
export interface OasisStats {
  posts: number;
  comments: number;
  likes: number;
  follows: number;
}

/** ページネーション付きレスポンス */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
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

/** チャート凡例のラベル */
export const DIMENSION_LABELS: Record<string, string> = {
  user_adoption: "ユーザーの広がり",
  revenue_potential: "収益性の見通し",
  tech_maturity: "技術の成熟度",
  competitive_pressure: "競合優位性",
  regulatory_risk: "規制適合性",
  market_awareness: "市場での認知度",
  ecosystem_health: "連携・コミュニティの活発さ",
  funding_climate: "投資・資金の集まりやすさ",
};

/** マーケットディメンションの表示色 */
export const DIMENSION_COLORS: Record<string, string> = {
  user_adoption: "#34d399",
  revenue_potential: "#60a5fa",
  tech_maturity: "#a78bfa",
  competitive_pressure: "#ef4444",
  regulatory_risk: "#f97316",
  market_awareness: "#fbbf24",
  ecosystem_health: "#06b6d4",
  funding_climate: "#9ca3af",
};
