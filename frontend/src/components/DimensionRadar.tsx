import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { DimensionPrediction } from "../api/types";
import { isThreatDimension } from "../api/types";

/** RadarChart用の短縮ラベル */
const SHORT_LABELS: Record<string, string> = {
  user_adoption: "ユーザー",
  revenue_potential: "収益性",
  tech_maturity: "技術成熟",
  competitive_pressure: "競合",
  regulatory_risk: "規制",
  market_awareness: "認知度",
  ecosystem_health: "エコシステム",
  funding_climate: "資金調達",
};

interface Props {
  predictions: DimensionPrediction[];
}

export default function DimensionRadar({ predictions }: Props) {
  const data = predictions.map((dp) => {
    // Threat metrics: invert so that high = good on radar
    const inverted = isThreatDimension(dp.dimension);
    const startRaw = dp.trend.values.length > 0 ? dp.trend.values[0] : dp.current_value;
    return {
      dimension: SHORT_LABELS[dp.dimension] || dp.dimension,
      start: Math.round((inverted ? 1 - startRaw : startRaw) * 100),
      end: Math.round((inverted ? 1 - dp.current_value : dp.current_value) * 100),
    };
  });

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid stroke="var(--color-border)" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }}
        />
        <Radar
          name="開始時"
          dataKey="start"
          stroke="var(--color-neutral)"
          fill="var(--color-neutral)"
          fillOpacity={0.1}
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />
        <Radar
          name="終了時"
          dataKey="end"
          stroke="var(--color-interactive)"
          fill="var(--color-interactive)"
          fillOpacity={0.15}
          strokeWidth={2}
        />
        <Legend
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
