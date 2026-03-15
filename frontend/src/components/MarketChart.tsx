import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { RoundResult } from "../api/types";
import { DIMENSION_COLORS, DIMENSION_LABELS } from "../api/types";

interface Props {
  rounds: RoundResult[];
  title: string;
  dimensions?: string[];
}

export default function MarketChart({
  rounds,
  title,
  dimensions,
}: Props) {
  const allDimensions = dimensions || Object.keys(DIMENSION_LABELS);

  if (rounds.length === 0) {
    return (
      <div className="bg-surface-0 rounded-lg border border-border p-5">
        <h3 className="text-sm font-medium text-text-primary mb-3">{title}</h3>
        <p className="text-sm text-text-tertiary py-8 text-center">
          データがありません
        </p>
      </div>
    );
  }

  const chartData = rounds.map((r) => {
    const point: Record<string, number> = { round: r.round_number };
    for (const dim of allDimensions) {
      point[dim] = Number((r.market_state.dimensions[dim] ?? 0).toFixed(3));
    }
    return point;
  });

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      <h3 className="text-sm font-medium text-text-primary mb-1">{title}</h3>
      <p className="text-[10px] text-text-tertiary mb-3">縦軸: LLMによる評価（低←→高） / 横軸: 経過月数</p>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="round"
            stroke="#94a3b8"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: "#e2e8f0" }}
            label={{
              value: "月",
              position: "insideBottomRight",
              offset: -5,
              fill: "#94a3b8",
              fontSize: 12,
            }}
          />
          <YAxis
            stroke="#94a3b8"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "6px",
              fontSize: "13px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
            }}
            labelStyle={{ color: "#475569", fontWeight: 500 }}
            labelFormatter={(v) => `${v}ヶ月目`}
          />
          <Legend
            iconType="plainline"
            wrapperStyle={{ fontSize: "12px", color: "#475569" }}
          />
          {allDimensions.map((dim) => (
            <Line
              key={dim}
              type="monotone"
              dataKey={dim}
              name={DIMENSION_LABELS[dim] || dim}
              stroke={DIMENSION_COLORS[dim] || "#94a3b8"}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
