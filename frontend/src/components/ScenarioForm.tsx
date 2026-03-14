import { useState } from "react";
import type { ScenarioInput } from "../api/types";

interface Props {
  onSubmit: (scenario: ScenarioInput) => void;
  isLoading: boolean;
}

export default function ScenarioForm({ onSubmit, isLoading }: Props) {
  const [description, setDescription] = useState("");
  const [numRounds, setNumRounds] = useState(24);
  const [aiAcceleration, setAiAcceleration] = useState(0);
  const [economicShock, setEconomicShock] = useState(0);
  const [policyChange, setPolicyChange] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      description,
      num_rounds: numRounds,
      ai_acceleration: aiAcceleration,
      economic_shock: economicShock,
      policy_change: policyChange || null,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl mx-auto">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          シナリオ説明
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          required
          minLength={10}
          maxLength={2000}
          placeholder="例: 生成AIの急速な普及により、SES企業のエンジニア需要が変化する..."
          className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-3 text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            シミュレーション期間（月）
          </label>
          <input
            type="number"
            value={numRounds}
            onChange={(e) => setNumRounds(Number(e.target.value))}
            min={1}
            max={36}
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2 text-gray-100 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            AI加速度 ({aiAcceleration > 0 ? "+" : ""}{aiAcceleration.toFixed(1)})
          </label>
          <input
            type="range"
            value={aiAcceleration}
            onChange={(e) => setAiAcceleration(Number(e.target.value))}
            min={-1}
            max={1}
            step={0.1}
            className="w-full accent-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            経済ショック ({economicShock > 0 ? "+" : ""}{economicShock.toFixed(1)})
          </label>
          <input
            type="range"
            value={economicShock}
            onChange={(e) => setEconomicShock(Number(e.target.value))}
            min={-1}
            max={1}
            step={0.1}
            className="w-full accent-blue-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          政策変更（任意）
        </label>
        <input
          type="text"
          value={policyChange}
          onChange={(e) => setPolicyChange(e.target.value)}
          placeholder="例: DX推進法改正、インボイス制度拡大"
          className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2 text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading || description.length < 10}
        className="w-full py-3 px-6 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium transition-colors"
      >
        {isLoading ? "送信中..." : "シミュレーション開始"}
      </button>
    </form>
  );
}
