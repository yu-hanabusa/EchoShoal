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
import { SKILL_COLORS, SKILL_LABELS } from "../api/types";

interface Props {
  rounds: RoundResult[];
  dataKey: "skill_demand" | "unit_prices";
  title: string;
  skills?: string[];
}

export default function MarketChart({
  rounds,
  dataKey,
  title,
  skills,
}: Props) {
  const allSkills = skills || Object.keys(SKILL_LABELS);

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
    for (const skill of allSkills) {
      const source = r.market_state[dataKey] as Record<string, number>;
      point[skill] = Number((source[skill] ?? 0).toFixed(3));
    }
    return point;
  });

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-5">
      <h3 className="text-sm font-medium text-text-primary mb-4">{title}</h3>
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
          {allSkills.map((skill) => (
            <Line
              key={skill}
              type="monotone"
              dataKey={skill}
              name={SKILL_LABELS[skill] || skill}
              stroke={SKILL_COLORS[skill] || "#94a3b8"}
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
