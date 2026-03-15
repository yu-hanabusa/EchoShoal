interface Props {
  percentage: number;
  currentRound: number;
  totalRounds: number;
  status: string;
  phase?: string;
}

export default function ProgressBar({
  percentage,
  currentRound,
  totalRounds,
  status,
  phase,
}: Props) {
  const pct = Math.min(percentage, 100);

  const statusText =
    status === "queued"
      ? "キューに追加中..."
      : status === "completed"
        ? "完了"
        : status === "failed"
          ? "エラーが発生しました"
          : phase || `${currentRound} / ${totalRounds} ヶ月目を実行中`;

  return (
    <div className="bg-surface-0 rounded-lg border border-border p-6 max-w-md mx-auto">
      <div className="flex items-baseline justify-between mb-3">
        <p className="text-sm text-text-secondary">{statusText}</p>
        <span className="text-sm font-medium text-text-primary tabular-nums">
          {pct.toFixed(0)}%
        </span>
      </div>
      <div className="w-full bg-surface-2 rounded-full h-2">
        <div
          className="bg-interactive h-2 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
