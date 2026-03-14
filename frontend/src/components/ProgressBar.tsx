interface Props {
  percentage: number;
  currentRound: number;
  totalRounds: number;
  status: string;
}

export default function ProgressBar({ percentage, currentRound, totalRounds, status }: Props) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-6 max-w-lg mx-auto">
      <div className="flex justify-between text-sm text-gray-400 mb-2">
        <span>ラウンド {currentRound} / {totalRounds}</span>
        <span>{percentage.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-800 rounded-full h-3">
        <div
          className="bg-blue-500 h-3 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <p className="text-center text-gray-400 mt-3 text-sm">
        {status === "queued" ? "キューに追加中..." :
         status === "running" ? "シミュレーション実行中..." :
         status === "completed" ? "完了" :
         "エラーが発生しました"}
      </p>
    </div>
  );
}
