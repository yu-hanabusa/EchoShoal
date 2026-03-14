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

export default function MarketChart({ rounds, dataKey, title, skills }: Props) {
  const allSkills = skills || Object.keys(SKILL_LABELS);

  const chartData = rounds.map((r) => {
    const point: Record<string, number> = { round: r.round_number };
    for (const skill of allSkills) {
      const source = r.market_state[dataKey] as Record<string, number>;
      point[skill] = Number((source[skill] ?? 0).toFixed(3));
    }
    return point;
  });

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
      <h3 className="text-lg font-medium text-gray-200 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="round"
            stroke="#9ca3af"
            label={{ value: "ラウンド", position: "insideBottom", offset: -5, fill: "#9ca3af" }}
          />
          <YAxis stroke="#9ca3af" />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "8px" }}
            labelStyle={{ color: "#d1d5db" }}
          />
          <Legend />
          {allSkills.map((skill) => (
            <Line
              key={skill}
              type="monotone"
              dataKey={skill}
              name={SKILL_LABELS[skill] || skill}
              stroke={SKILL_COLORS[skill] || "#8884d8"}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
