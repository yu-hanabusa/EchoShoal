import { useState } from "react";
import type { ScenarioInput } from "../api/types";

interface Props {
  onSubmit: (scenario: ScenarioInput) => void;
  isLoading: boolean;
  submitLabel?: string;
}

export default function ScenarioForm({ onSubmit, isLoading, submitLabel }: Props) {
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

  const charCount = description.length;
  const isValid = charCount >= 10;

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Primary: scenario description — this is the main input */}
      <div>
        <label
          htmlFor="scenario-desc"
          className="block text-base font-medium text-text-primary mb-1"
        >
          シナリオ
        </label>
        <p className="text-sm text-text-tertiary mb-3">
          予測したい市場変化のシナリオを記述してください
        </p>
        <textarea
          id="scenario-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          required
          minLength={10}
          maxLength={2000}
          placeholder="例: 生成AIの急速な普及により、SES企業のエンジニア需要が変化する。大手SIerはAI導入支援に舵を切り、中小SES企業はレガシー保守案件の減少に直面する..."
          className="w-full rounded-md bg-surface-0 border border-border px-4 py-3 text-text-primary placeholder-text-tertiary text-[15px] leading-relaxed focus:border-interactive focus:ring-1 focus:ring-interactive outline-none resize-y min-h-[120px]"
        />
        <div className="mt-1.5 flex justify-end">
          <span
            className={`text-xs tabular-nums ${
              charCount > 0 && charCount < 10
                ? "text-caution"
                : "text-text-tertiary"
            }`}
          >
            {charCount > 0 && `${charCount} / 2000`}
          </span>
        </div>
      </div>

      {/* Secondary: simulation parameters */}
      <fieldset className="rounded-md border border-border bg-surface-0 p-5">
        <legend className="px-2 text-sm font-medium text-text-secondary">
          パラメータ
        </legend>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-x-6 gap-y-5 mt-1">
          <div>
            <label
              htmlFor="num-rounds"
              className="block text-sm text-text-secondary mb-1.5"
            >
              シミュレーション期間
            </label>
            <div className="flex items-baseline gap-2">
              <input
                id="num-rounds"
                type="number"
                value={numRounds}
                onChange={(e) => setNumRounds(Number(e.target.value))}
                min={1}
                max={36}
                className="w-20 rounded-md bg-surface-0 border border-border px-3 py-1.5 text-sm text-text-primary focus:border-interactive focus:ring-1 focus:ring-interactive outline-none tabular-nums"
              />
              <span className="text-sm text-text-tertiary">ヶ月</span>
            </div>
          </div>

          <div>
            <label
              htmlFor="ai-accel"
              className="block text-sm text-text-secondary mb-1.5"
            >
              AI加速度
            </label>
            <div className="flex items-center gap-3">
              <input
                id="ai-accel"
                type="range"
                value={aiAcceleration}
                onChange={(e) => setAiAcceleration(Number(e.target.value))}
                min={-1}
                max={1}
                step={0.1}
                className="flex-1"
              />
              <span className="text-sm text-text-primary tabular-nums w-10 text-right font-medium">
                {aiAcceleration > 0 ? "+" : ""}
                {aiAcceleration.toFixed(1)}
              </span>
            </div>
          </div>

          <div>
            <label
              htmlFor="econ-shock"
              className="block text-sm text-text-secondary mb-1.5"
            >
              経済ショック
            </label>
            <div className="flex items-center gap-3">
              <input
                id="econ-shock"
                type="range"
                value={economicShock}
                onChange={(e) => setEconomicShock(Number(e.target.value))}
                min={-1}
                max={1}
                step={0.1}
                className="flex-1"
              />
              <span className="text-sm text-text-primary tabular-nums w-10 text-right font-medium">
                {economicShock > 0 ? "+" : ""}
                {economicShock.toFixed(1)}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-5">
          <label
            htmlFor="policy"
            className="block text-sm text-text-secondary mb-1.5"
          >
            政策変更
            <span className="text-text-tertiary ml-1">（任意）</span>
          </label>
          <input
            id="policy"
            type="text"
            value={policyChange}
            onChange={(e) => setPolicyChange(e.target.value)}
            placeholder="例: DX推進法改正、インボイス制度拡大"
            className="w-full rounded-md bg-surface-0 border border-border px-3 py-1.5 text-sm text-text-primary placeholder-text-tertiary focus:border-interactive focus:ring-1 focus:ring-interactive outline-none"
          />
        </div>
      </fieldset>

      {/* Action */}
      <button
        type="submit"
        disabled={isLoading || !isValid}
        className="w-full py-2.5 px-6 rounded-md bg-interactive hover:bg-interactive-hover disabled:bg-border-strong disabled:text-text-tertiary text-white text-sm font-medium transition-colors cursor-pointer disabled:cursor-not-allowed"
      >
        {isLoading ? "送信中..." : (submitLabel || "シミュレーション開始")}
      </button>
    </form>
  );
}
