import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  type: "risk" | "opportunity";
  items: string[];
}

const icons = {
  risk: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
      <path
        d="M8 1L15 14H1L8 1Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M8 6V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="8" cy="11.5" r="0.75" fill="currentColor" />
    </svg>
  ),
  opportunity: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
      <path
        d="M8 1L9.8 5.8L15 6.2L11.2 9.6L12.4 15L8 12.2L3.6 15L4.8 9.6L1 6.2L6.2 5.8L8 1Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
    </svg>
  ),
};

export default function RiskOpportunityCard({ type, items }: Props) {
  if (items.length === 0) return null;

  const isRisk = type === "risk";
  const containerCls = isRisk
    ? "bg-negative/5 border border-negative/20 rounded-lg p-4"
    : "bg-positive/5 border border-positive/20 rounded-lg p-4";
  const titleCls = isRisk ? "text-negative" : "text-positive";
  const iconCls = isRisk ? "text-negative/70" : "text-positive/70";

  return (
    <div className={containerCls}>
      <p className={`text-xs font-semibold ${titleCls} mb-2 flex items-center gap-1.5`}>
        <span className={iconCls}>{icons[type]}</span>
        {isRisk ? "リスク" : "機会"}
      </p>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-text-secondary leading-relaxed flex items-start gap-1.5">
            <span className="text-text-tertiary shrink-0 mt-px">-</span>
            <span className="prose prose-sm max-w-none"><Markdown remarkPlugins={[remarkGfm]}>{item}</Markdown></span>
          </li>
        ))}
      </ul>
    </div>
  );
}
