"""レポートモデル — シミュレーション分析レポートの構造定義."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    """レポートの1セクション."""
    title: str
    content: str
    data: dict | None = None  # グラフ用の構造化データ（オプション）


class SimulationReport(BaseModel):
    """シミュレーション分析レポート."""
    title: str = "IT人材市場予測レポート"
    scenario_description: str = ""
    executive_summary: str = ""
    sections: list[ReportSection] = Field(default_factory=list)
    generated_at: str = ""

    def to_markdown(self) -> str:
        """レポートを Markdown 形式で出力する."""
        lines = [f"# {self.title}", ""]
        if self.scenario_description:
            lines.extend([f"> {self.scenario_description}", ""])
        if self.generated_at:
            lines.extend([f"*生成日時: {self.generated_at}*", ""])
        if self.executive_summary:
            lines.extend(["## エグゼクティブサマリー", "", self.executive_summary, ""])
        for section in self.sections:
            lines.extend([f"## {section.title}", "", section.content, ""])
        return "\n".join(lines)
