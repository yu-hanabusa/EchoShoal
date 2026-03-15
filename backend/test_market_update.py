import asyncio
import json
from app.core.llm.router import LLMRouter, TaskType

async def test():
    llm = LLMRouter()
    current_dims = {"user_adoption": 0.1, "revenue_potential": 0.72, "tech_maturity": 0.39, "competitive_pressure": 0.715}
    prompt = (
        "Round 3. Service: TeamChat\n"
        f"Current dimensions: {json.dumps(current_dims)}\n"
        "Actions this round:\n"
        "- Slack (reputation 0.8): build_competitor 'Developing Japanese-localized features'\n"
        "- Conservative enterprises x20 (reputation 0.5) [represents 20 entities]: adopt_service 'Adopting TeamChat'\n\n"
        "Estimate market impact. Return EXACTLY this JSON with your delta values (-0.1 to +0.1):\n"
        '{"dimension_deltas": {"user_adoption": 0.02, "revenue_potential": 0.01, "tech_maturity": 0.0, '
        '"competitive_pressure": 0.0, "regulatory_risk": 0.0, "market_awareness": 0.01, '
        '"ecosystem_health": 0.0, "funding_climate": 0.0}, '
        '"macro_deltas": {"economic_sentiment": 0.0, "tech_hype_level": 0.0, '
        '"regulatory_pressure": 0.0, "ai_disruption_level": 0.0}}'
    )
    result = await llm.generate_json(
        task_type=TaskType.AGENT_DECISION,
        prompt=prompt,
        system_prompt="You are a market analyst. Estimate how agent actions impact market dimensions. Respond only with valid JSON.",
    )
    print("Result:", json.dumps(result, indent=2))

asyncio.run(test())
