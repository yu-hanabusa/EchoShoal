import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { DIMENSION_LABELS, DIMENSION_COLORS, isThreatDimension } from "../api/types";

interface Props {
  dimension: string;
  values: number[];
  currentValue: number;
  changeRate: number;
}

export default function DimensionSparkline({ dimension, values, currentValue, changeRate }: Props) {
  const color = DIMENSION_COLORS[dimension] || "#64748b";
  const label = DIMENSION_LABELS[dimension] || dimension;

  // Threat metrics: invert for display
  const inverted = isThreatDimension(dimension);
  const displayValues = inverted ? values.map((v) => 1 - v) : values;
  const displayCurrent = inverted ? 1 - currentValue : currentValue;
  const displayRate = inverted ? -changeRate : changeRate;

  const data = displayValues.map((v, i) => ({ round: i + 1, value: v }));

  const level = displayCurrent >= 0.6 ? "高" : displayCurrent >= 0.3 ? "中" : "低";
  const levelColor =
    displayCurrent >= 0.6 ? "bg-positive-light text-positive" :
    displayCurrent >= 0.3 ? "bg-caution-light text-caution" :
    "bg-negative-light text-negative";

  const arrow = displayRate > 5 ? "↑" : displayRate < -5 ? "↓" : "→";
  const arrowColor = displayRate > 5 ? "text-positive" : displayRate < -5 ? "text-negative" : "text-text-tertiary";

  if (data.length === 0) {
    return (
      <div className="bg-surface-0 rounded-lg border border-border p-3">
        <p className="text-xs font-medium text-text-primary truncate">{label}</p>
        <p className="text-xs text-text-tertiary mt-1">データなし</p>
      </div>
    );
  }

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-medium text-text-primary truncate">{label}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`text-xs font-bold rounded px-1 py-0.5 ${levelColor}`}>{level}</span>
          <span className={`text-xs font-medium ${arrowColor}`}>{arrow}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={56}>
        <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <defs>
            <linearGradient id={`grad-${dimension}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#grad-${dimension})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
