"""レポート生成器 — 構造化データをClaude APIで分析しレポートを作成する."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.llm.router import LLMRouter, TaskType
from app.reports.models import ReportSection, SimulationReport
from app.simulation.models import SuccessScore

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM_PROMPT = """あなたはサービスビジネスインパクトの専門アナリストです。
シミュレーション結果のデータに基づき、洞察に富んだ分析レポートを日本語で作成してください。

以下のルールに従ってください:
- データに基づいた客観的な分析を行う
- 具体的な数値を引用して論拠を示す
- 各ステークホルダー（企業、フリーランス、個人開発者、行政、投資家、プラットフォーマー、コミュニティ）への影響を考慮する
- 対象サービスの成功可否の判断材料を明確にする
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

        # 各セクションを順次生成（コンテキストの一貫性のため）
        summary = await self._generate_executive_summary(report_data)
        report.executive_summary = summary

        sections = [
            await self._generate_market_impact_analysis(report_data),
            await self._generate_dimension_analysis(report_data),
            await self._generate_stakeholder_impact(report_data),
            await self._generate_document_impact_analysis(report_data),
            await self._generate_additional_info_suggestions(report_data),
            await self._generate_recommendations(report_data),
        ]
        report.sections = sections

        # サービス成功スコアをLLMで算出
        report.success_score = await self._generate_success_score(report_data)

        logger.info("レポート生成完了: %dセクション, スコア=%s", len(sections),
                     report.success_score.score if report.success_score else "N/A")
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

    async def _generate_market_impact_analysis(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """市場インパクト分析セクション."""
        macro = data.get("macro_timeline", {})
        prompt = (
            "以下のマクロ指標の推移データに基づき、対象サービスの市場インパクト分析を行ってください。\n\n"
            f"経済センチメント推移: {_summarize_timeline(macro.get('economic_sentiment', []))}\n"
            f"技術ハイプレベル推移: {_summarize_timeline(macro.get('tech_hype_level', []))}\n"
            f"規制圧力推移: {_summarize_timeline(macro.get('regulatory_pressure', []))}\n"
            f"AI破壊度推移: {_summarize_timeline(macro.get('ai_disruption_level', []))}\n\n"
            f"主要な変化ラウンド:\n{json.dumps(data.get('significant_rounds', []), ensure_ascii=False, indent=2)}\n"
        )
        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return ReportSection(
            title="市場インパクト分析",
            content=content,
            data={"macro_timeline": macro},
        )

    async def _generate_dimension_analysis(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """ディメンション分析セクション."""
        dims = data.get("dimension_timeline", {})
        prompt = (
            "以下のマーケットディメンション別推移データに基づき、サービスの成功可否の判断材料を分析してください。\n\n"
        )
        for dim_key in dims:
            d_summary = _summarize_timeline(dims[dim_key])
            prompt += f"- {dim_key}: {d_summary}\n"

        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return ReportSection(
            title="ディメンション分析",
            content=content,
            data={"dimension_timeline": dims},
        )

    async def _generate_stakeholder_impact(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """ステークホルダー影響分析セクション."""
        agents = data.get("agents", [])
        actions = data.get("action_summary", {})
        prompt = (
            "以下のエージェント情報とアクション集計に基づき、"
            "各ステークホルダー（企業・フリーランス・個人開発者・行政・投資家・プラットフォーマー・コミュニティ）"
            "への影響を分析してください。\n\n"
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
            title="ステークホルダー影響分析",
            content=content,
            data={"agents": agents, "action_summary": actions},
        )

    async def _generate_document_impact_analysis(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """資料影響分析セクション — 入力文書がシミュレーションにどう影響したかをLLMが分析."""
        doc_impact = data.get("document_impact", [])
        agents = data.get("agents", [])
        actions = data.get("action_summary", {})

        prompt = (
            "以下の文書参照ログとエージェント行動データに基づき、"
            "入力された資料がシミュレーション結果にどのように影響したかを分析してください。\n"
            "各文書がどのエージェントのどの意思決定にどう影響したかを具体的に示してください。\n\n"
            f"文書参照ログ:\n{json.dumps(doc_impact[:50], ensure_ascii=False, indent=2)}\n\n"
            f"エージェント最終状態:\n{json.dumps(agents, ensure_ascii=False, indent=2)}\n\n"
            f"アクション実行回数:\n{json.dumps(actions, ensure_ascii=False, indent=2)}\n"
        )

        if not doc_impact:
            prompt += "\n（文書参照ログなし — 文書が入力されていないか、RAGが無効です。一般的な分析を行ってください。）"

        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.5,
        )
        return ReportSection(
            title="資料影響分析",
            content=content,
            data={"document_impact": doc_impact},
        )

    async def _generate_additional_info_suggestions(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """追加情報提案セクション — より精密なシミュレーションに必要な情報をLLMが提案."""
        dims = data.get("dimension_timeline", {})
        doc_impact = data.get("document_impact", [])
        final_market = data.get("final_market", {})

        prompt = (
            "以下のシミュレーション結果を分析し、"
            "予測の不確実性が高い領域を特定してください。\n"
            "そして、どのような追加情報があればシミュレーションの精度が向上するかを具体的に提案してください。\n\n"
            f"シナリオ: {data.get('scenario_description', '')}\n"
            f"ディメンション最終値:\n{json.dumps(final_market.get('dimensions', {}), ensure_ascii=False, indent=2)}\n"
            f"文書参照数: {len(doc_impact)}件\n"
            f"シミュレーション期間: {data.get('total_rounds', 0)}ヶ月\n\n"
            "以下の観点で提案してください:\n"
            "1. 競合情報: どの競合のどのようなデータがあれば予測が改善されるか\n"
            "2. ユーザー情報: ターゲットユーザーのどのようなデータが有用か\n"
            "3. 市場データ: どのような市場調査や統計が役立つか\n"
            "4. 技術情報: 技術的な評価に必要な情報は何か\n"
            "5. 規制情報: 規制環境の理解に必要な情報は何か\n"
        )
        content = await self._llm.generate(
            task_type=TaskType.REPORT_GENERATION,
            prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.6,
        )
        return ReportSection(title="追加情報提案", content=content)

    async def _generate_recommendations(
        self, data: dict[str, Any]
    ) -> ReportSection:
        """提言セクション."""
        prompt = (
            "以下のシミュレーション結果に基づき、対象サービスの成功に向けた具体的な提言を行ってください。\n"
            "対象: サービス提供者、潜在的投資家、潜在的ユーザー企業\n\n"
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

    async def _generate_success_score(self, data: dict[str, Any]) -> SuccessScore | None:
        """LLMにシミュレーション結果を渡し、サービス成功スコアを算出させる."""
        final_market = data.get("final_market", {})
        dims = final_market.get("dimensions", {})
        actions = data.get("action_summary", {})

        # ディメンションの推移データ（トレンド）を構築
        dim_timeline = data.get("dimension_timeline", {})
        trend_lines = []
        for dim_key, values in dim_timeline.items():
            if values and len(values) >= 2:
                start_val = values[0]
                end_val = values[-1]
                change = end_val - start_val
                direction = "↑上昇" if change > 0.02 else "↓下降" if change < -0.02 else "→横ばい"
                trend_lines.append(
                    f"  {dim_key}: {start_val:.3f}→{end_val:.3f} ({change:+.3f}, {direction})"
                )
        trend_text = "\n".join(trend_lines) if trend_lines else "  推移データなし"

        prompt = (
            "以下のシミュレーション結果を分析し、対象サービスの成功可能性を0-100のスコアで評価してください。\n\n"
            f"シナリオ: {data.get('scenario_description', '')}\n"
            f"シミュレーション期間: {data.get('total_rounds', 0)}ヶ月\n\n"
            f"最終ディメンション値:\n{json.dumps(dims, ensure_ascii=False, indent=2)}\n\n"
            f"ディメンション推移（開始→終了）:\n{trend_text}\n\n"
            f"マクロ指標: 経済センチメント={final_market.get('economic_sentiment', 0.5):.2f}, "
            f"技術ハイプ={final_market.get('tech_hype_level', 0.5):.2f}, "
            f"規制圧力={final_market.get('regulatory_pressure', 0.3):.2f}\n\n"
            f"主要アクション: {json.dumps(dict(list(actions.items())[:8]), ensure_ascii=False)}\n\n"
            "評価の指針:\n"
            "- 絶対値だけでなく推移（トレンド）を重視してください\n"
            "- user_adoptionやmarket_awarenessが上昇傾向なら、まだ低い値でもポジティブ評価\n"
            "- competitive_pressureが高くても、user_adoptionも高ければ健全な競争\n"
            "- 新サービスの初期段階では低い値が自然。成長トレンドを重視\n\n"
            "以下のJSON形式で回答してください:\n"
            "{\n"
            '  "score": <0-100の整数。70以上=成功見込み、40-69=要注意、39以下=困難>,\n'
            '  "verdict": "成功見込み|要注意|困難",\n'
            '  "key_factors": ["判定の根拠1", "判定の根拠2", ...],\n'
            '  "risks": ["リスク1", "リスク2", ...],\n'
            '  "opportunities": ["機会1", "機会2", ...]\n'
            "}"
        )

        try:
            response = await self._llm.generate_json(
                task_type=TaskType.REPORT_GENERATION,
                prompt=prompt,
                system_prompt=(
                    "あなたはサービスビジネスの専門アナリストです。"
                    "シミュレーション結果のデータに基づき、客観的にサービスの成功可能性を評価してください。"
                ),
            )
            score = max(0, min(100, int(response.get("score", 50))))
            return SuccessScore(
                score=score,
                verdict=str(response.get("verdict", "")),
                key_factors=[str(f) for f in response.get("key_factors", [])[:5]],
                risks=[str(r) for r in response.get("risks", [])[:5]],
                opportunities=[str(o) for o in response.get("opportunities", [])[:5]],
            )
        except Exception:
            logger.warning("成功スコア生成失敗")
            return None

    def _build_summary_prompt(self, data: dict[str, Any]) -> str:
        """サマリー用プロンプトを構築."""
        return (
            "以下のシミュレーション結果の要約データに基づき、"
            "対象サービスの成功可否を含む3〜5文のエグゼクティブサマリーを作成してください。\n\n"
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
