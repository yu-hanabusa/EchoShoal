interface Props {
  score: number;
  size?: number;
  strokeWidth?: number;
}

export default function ScoreGauge({ score, size = 160, strokeWidth = 12 }: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const center = size / 2;

  const color =
    score >= 70 ? "var(--color-positive)" :
    score >= 40 ? "var(--color-caution)" :
    "var(--color-negative)";

  return (
    <svg width={size} height={size} className="block">
      {/* Background ring */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="var(--color-surface-2)"
        strokeWidth={strokeWidth}
      />
      {/* Score ring */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${center} ${center})`}
        style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
      />
      {/* Glow effect */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth + 8}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${center} ${center})`}
        opacity={0.1}
        style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
      />
      {/* Score text */}
      <text
        x={center}
        y={center - 6}
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        fontSize={size * 0.28}
        fontWeight="bold"
        fontFamily="Inter, system-ui, sans-serif"
      >
        {score}
      </text>
      <text
        x={center}
        y={center + size * 0.14}
        textAnchor="middle"
        dominantBaseline="central"
        fill="var(--color-text-tertiary)"
        fontSize={size * 0.09}
        fontFamily="Inter, system-ui, sans-serif"
      >
        / 100
      </text>
    </svg>
  );
}
