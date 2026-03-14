"""レポート生成器 — 構造化データをClaude APIで分析しレポートを作成する."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.llm.router import LLMRouter, TaskType
from app.reports.models import ReportSection, SimulationReport

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM_PROMPT = """あなたは日本のIT人材市場の専門アナリストです。
シミュレーション結果のデータに基づき、洞察に富んだ分析レポートを日本語で作成してください。

以下のルールに従ってください:
- データに基づいた客観的な分析を行う
- 具体的な数値を引用して論拠を示す
- SES企業、SIer企業、フリーランス、事業会社IT部門それぞれへの影響を考慮する
- 実行可能な提言を含める
- Markdown形式で記述する"""


class ReportGenerator:
    """シミュレーション結果からレポートを生成する."""

    def __init__(self, llm: LLMRouter):
        self._llm = llm

    async def generate(self, report_data: dict[str, Any]) -> SimulationReport:
        """構造化データからレポートを生成する."""
        report = SimulationReport(
            scenario_description=report_data.get("scenario_description", ""),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # 各セクションを並列ではなく順次生成（コンテキストの一貫性のため）
        summary = await self._generate_executive_summary(report_data)
        report.executive_summary = summary

        sections = [
            await self._generate_market_analysis(report_data),
            await self._generate_skill_analysis(report_data),
            await self._generate_industry_impact(report_data),
            await self._generate_recommendations(report_data),
        ]
        report.sections = sections

        logger.info("レポート生成完了: %dセクション", len(sections))
        return report

    async def _generate_executive_summary(
        self, data: dict[str, Any]
    ) -> str:
        """エグゼクティブサマリーを生成."""
        prompt = self._build_summary_prompt(data)
        return await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )

    async def _generate_market_analysis(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """市場動向分析セクション."""
        macro = data.get("macro_timeline", {})
        prompt = (
            "以下のマクロ指標の推移データに基づき、IT人材市場の動向分析を行ってください。\n\n"
            f"失業率推移: {_summarize_timeline(macro.get('unemployment_rate', []))}\n"
            f"AI自動化率推移: {_summarize_timeline(macro.get('ai_automation_rate', []))}\n"
            f"リモートワーク率推移: {_summarize_timeline(macro.get('remote_work_rate', []))}\n"
            f"オフショア率推移: {_summarize_timeline(macro.get('overseas_outsource_rate', []))}\n\n"
            f"主要な変化ラウンド:\n{json.dumps(data.get('significant_rounds', []), ensure_ascii=False, indent=2)}\n"
        )
        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return ReportSection(
            title="市場動向分析",
            content=content,
            data={"macro_timeline": macro},
        )

    async def _generate_skill_analysis(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """スキル需給分析セクション."""
        demand = data.get("skill_demand_timeline", {})
        prices = data.get("price_timeline", {})
        prompt = (
            "以下のスキル別需要・単価データに基づき、スキル需給分析を行ってください。\n\n"
        )
        for skill_key in demand:
            d_summary = _summarize_timeline(demand[skill_key])
            p_summary = _summarize_timeline(prices.get(skill_key, []))
            prompt += f"- {skill_key}: 需要{d_summary}, 単価{p_summary}\n"

        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return ReportSection(
            title="スキル需給分析",
            content=content,
            data={"skill_demand": demand, "prices": prices},
        )

    async def _generate_industry_impact(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """業界別影響分析セクション."""
        agents = data.get("agents", [])
        actions = data.get("action_summary", {})
        prompt = (
            "以下のエージェント情報とアクション集計に基づき、"
            "SIer/SES/フリーランス/事業会社それぞれへの影響を分析してください。\n\n"
            f"エージェント最終状態:\n{json.dumps(agents, ensure_ascii=False, indent=2)}\n\n"
            f"アクション実行回数:\n{json.dumps(actions, ensure_ascii=False, indent=2)}\n"
        )
        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return ReportSection(
            title="業界別影響分析",
            content=content,
            data={"agents": agents, "action_summary": actions},
        )

    async def _generate_recommendations(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """提言セクション."""
        prompt = (
            "以下のシミュレーション結果に基づき、具体的な提言を行ってください。\n"
            "対象: SES企業経営者、SIer企業、フリーランスエンジニア、事業会社IT部門\n\n"
            f"シナリオ: {data.get('scenario_description', '')}\n"
            f"シミュレーション期間: {data.get('total_rounds', 0)}ヶ月\n"
            f"最も多いアクション: {json.dumps(dict(list(data.get('action_summary', {}).items())[:5]), ensure_ascii=False)}\n"
        )
        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.6,
        )
        return ReportSection(title="提言", content=content)

    def _build_summary_prompt(self, data: dict[str, Any]) -> str:
        """サマリー用プロンプトを構築."""
        return (
            "以下のシミュレーション結果の要約データに基づき、"
            "3〜5文のエグゼクティブサマリーを作成してください。\n\n"
            f"シナリオ: {data.get('scenario_description', '')}\n"
            f"期間: {data.get('total_rounds', 0)}ヶ月\n"
            f"エージェント数: {len(data.get('agents', []))}\n"
            f"総アクション種別数: {len(data.get('action_summary', {}))}\n"
            f"主要変化ラウンド: {json.dumps(data.get('significant_rounds', []), ensure_ascii=False)}\n"
        )


def _summarize_timeline(values: list[float]) -> str:
    """時系列データを「開始値→終了値（変化率）」形式で要約."""
    if not values:
        return "データなし"
    start = values[0]
    end = values[-1]
    if start == 0:
        return f"{start:.3f}→{end:.3f}"
    change_pct = (end - start) / abs(start) * 100
    return f"{start:.3f}→{end:.3f}({change_pct:+.1f}%)"
