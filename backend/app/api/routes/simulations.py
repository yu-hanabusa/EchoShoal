"""シミュレーション API エンドポイント.

3ステップフロー:
  1. POST /api/simulations/        → ジョブ作成（CREATED状態）
  2. POST /api/simulations/{id}/documents → 文書アップロード
  3. POST /api/simulations/{id}/start     → シミュレーション実行開始

すべてのデータは job_id (= simulation_id) でスコープされる。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.documents.models import DocumentInfo, ProcessResult
from app.core.documents.parser import DocumentParseError, DocumentParser
from app.core.documents.processor import DocumentProcessor
from app.core.graph.agent_memory import AgentMemoryStore
from app.core.graph.client import GraphClient
from app.core.graph.rag import GraphRAGRetriever
from app.core.job_manager import JobManager, JobStatus
from app.core.llm.router import LLMRouter
from app.core.redis_client import RedisClient
from app.simulation.engine import SimulationEngine
from app.simulation.events.scheduler import EventScheduler
from app.simulation.factory import create_default_agents
from app.simulation.models import ScenarioInput
from app.simulation.scenario_analyzer import ScenarioAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

_redis: RedisClient | None = None
_job_manager: JobManager | None = None
_active_simulations: int = 0
_request_timestamps: deque[float] = deque()


def _get_job_manager() -> JobManager:
    global _redis, _job_manager
    if _job_manager is None:
        _redis = RedisClient()
        _job_manager = JobManager(_redis)
    return _job_manager


def _check_rate_limit() -> None:
    global _active_simulations
    now = time.monotonic()
    while _request_timestamps and now - _request_timestamps[0] > 60:
        _request_timestamps.popleft()
    if _active_simulations >= settings.max_concurrent_simulations:
        raise HTTPException(status_code=429, detail="同時実行上限に達しています")
    if len(_request_timestamps) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="リクエスト上限に達しています")
    _request_timestamps.append(now)


async def _get_graph_client() -> GraphClient | None:
    """GraphClientを取得。利用不可時はNoneを返す。"""
    try:
        client = GraphClient()
        if await client.is_available():
            return client
    except Exception:
        pass
    return None


# ─── Step 1: ジョブ作成 ───

@router.post("/")
async def create_simulation(scenario: ScenarioInput) -> JSONResponse:
    """シミュレーションジョブを作成する（CREATED状態）.

    文書アップロード後に /start で実行を開始する。
    """
    job_manager = _get_job_manager()
    job_id = await job_manager.create_job(
        scenario_description=scenario.description[:200],
    )
    await job_manager.save_scenario(job_id, scenario.model_dump())

    return JSONResponse(
        status_code=201,
        content={"job_id": job_id, "status": "created"},
    )


# ─── Step 2: 文書アップロード ───

@router.post("/{job_id}/documents", response_model=ProcessResult)
async def upload_simulation_document(
    job_id: str,
    file: UploadFile = File(...),
    source: str = Form(default=""),
) -> ProcessResult:
    """このシミュレーション用の文書をアップロードし、NLP解析→知識グラフに格納する."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    if info.status not in (JobStatus.CREATED,):
        raise HTTPException(status_code=400, detail="文書アップロードは作成済みジョブのみ可能です")

    content = await file.read()
    parser = DocumentParser()
    try:
        doc = parser.parse(content, file.filename or "unknown", source=source)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    graph_client = await _get_graph_client()
    if not graph_client:
        raise HTTPException(status_code=503, detail="Neo4jに接続できません")

    try:
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        return await processor.process(doc)
    finally:
        await graph_client.close()


@router.get("/{job_id}/documents", response_model=list[DocumentInfo])
async def list_simulation_documents(job_id: str) -> list[DocumentInfo]:
    """このシミュレーションにアップロードされた文書一覧を取得する."""
    graph_client = await _get_graph_client()
    if not graph_client:
        return []
    try:
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        return await processor.get_documents()
    finally:
        await graph_client.close()


# ─── Step 3: シミュレーション実行開始 ───

@router.post("/{job_id}/start")
async def start_simulation(job_id: str) -> JSONResponse:
    """シミュレーションの実行を開始する."""
    global _active_simulations
    _check_rate_limit()

    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    if info.status != JobStatus.CREATED:
        raise HTTPException(status_code=400, detail=f"ジョブの状態が不正です: {info.status.value}")

    scenario_data = await job_manager.get_scenario(job_id)
    if not scenario_data:
        raise HTTPException(status_code=400, detail="シナリオが保存されていません")

    scenario = ScenarioInput(**scenario_data)
    await job_manager.set_queued(job_id)

    _active_simulations += 1
    asyncio.create_task(_run_simulation_task(job_id, scenario, job_manager))

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "queued"},
    )


# ─── シミュレーション実行（バックグラウンド） ───

async def _setup_graph_components(
    simulation_id: str,
) -> tuple[GraphRAGRetriever | None, AgentMemoryStore | None, GraphClient | None]:
    """知識グラフ関連コンポーネントをセットアップする（simulation_idスコープ）."""
    try:
        graph_client = GraphClient()
        if not await graph_client.is_available():
            return None, None, None
        agent_memory = AgentMemoryStore(graph_client, simulation_id=simulation_id)
        rag = GraphRAGRetriever(graph_client, agent_memory, simulation_id=simulation_id)
        return rag, agent_memory, graph_client
    except Exception:
        return None, None, None


async def _run_simulation_task(
    job_id: str, scenario: ScenarioInput, job_manager: JobManager
) -> None:
    """バックグラウンドでシミュレーションを実行する."""
    global _active_simulations
    graph_client: GraphClient | None = None
    try:
        await job_manager.set_running(job_id)

        llm = LLMRouter()
        agents = create_default_agents(llm)

        analyzer = ScenarioAnalyzer()
        enriched = analyzer.analyze(scenario)
        logger.info(
            "シナリオ解析: スキル%d件, 業界%d件検出",
            len(enriched.detected_skills), len(enriched.detected_industries),
        )

        event_scheduler = EventScheduler(llm=llm)
        await event_scheduler.generate_from_scenario(scenario)

        # simulation_id = job_id でスコープ
        rag, agent_memory, graph_client = await _setup_graph_components(job_id)

        async def on_progress(current: int, total: int) -> None:
            await job_manager.update_progress(job_id, current, total)

        engine = SimulationEngine(
            agents=agents, llm=llm, scenario=scenario,
            on_progress=on_progress, event_scheduler=event_scheduler,
            enriched_scenario=enriched,
            rag=rag, agent_memory=agent_memory,
        )

        results = await engine.run()

        result_data = {
            "scenario": scenario.model_dump(),
            "summary": engine.get_summary(),
            "rounds": [r.model_dump() for r in results],
        }
        await job_manager.set_completed(job_id, result_data)

    except Exception as exc:
        logger.exception("シミュレーション失敗: job=%s", job_id)
        await job_manager.set_failed(job_id, str(exc))
    finally:
        _active_simulations -= 1
        if graph_client:
            try:
                await graph_client.close()
            except Exception:
                pass


# ─── 結果取得 ───

@router.get("/")
async def list_simulations() -> list[dict[str, Any]]:
    """過去のシミュレーション一覧を取得する."""
    job_manager = _get_job_manager()
    jobs = await job_manager.list_jobs()
    return [j.model_dump() for j in jobs]


@router.get("/{job_id}")
async def get_simulation(job_id: str) -> dict[str, Any]:
    """ジョブのステータスと結果を取得する."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)

    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    response: dict[str, Any] = info.model_dump()

    if info.status == JobStatus.COMPLETED:
        result = await job_manager.get_result(job_id)
        if result:
            response["result"] = result

    return response


@router.get("/{job_id}/progress")
async def get_simulation_progress(job_id: str) -> dict[str, Any]:
    """シミュレーションの進捗を取得する."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)

    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    return {
        "job_id": job_id,
        "status": info.status.value,
        "progress": info.progress,
    }


# ─── グラフ可視化（シミュレーションスコープ） ───

@router.get("/{job_id}/graph")
async def get_simulation_graph(job_id: str) -> dict[str, Any]:
    """このシミュレーションの知識グラフ可視化データを取得する."""
    graph_client = await _get_graph_client()
    if not graph_client:
        return {"elements": []}

    try:
        elements: list[dict[str, Any]] = []

        # このシミュレーションのDocumentノードとMENTIONS
        docs = await graph_client.execute_read(
            "MATCH (d:Document {simulation_id: $sim_id}) "
            "OPTIONAL MATCH (d)-[:MENTIONS]->(e) "
            "RETURN d.doc_id AS doc_id, d.filename AS filename, "
            "       collect({name: e.name, type: labels(e)[0]}) AS mentions",
            {"sim_id": job_id},
        )
        for row in docs:
            doc_node_id = f"doc_{row['doc_id']}"
            elements.append({
                "data": {"id": doc_node_id, "label": row["filename"], "type": "Document"},
            })
            for mention in (row["mentions"] or []):
                if mention.get("name"):
                    prefix_map = {"Skill": "skill_", "Company": "company_", "Policy": "policy_"}
                    target_prefix = prefix_map.get(mention.get("type", ""), "")
                    target_id = f"{target_prefix}{mention['name']}"
                    # エンティティノード
                    elements.append({
                        "data": {"id": target_id, "label": mention["name"], "type": mention.get("type", "Unknown")},
                    })
                    elements.append({
                        "data": {"source": doc_node_id, "target": target_id, "label": "MENTIONS"},
                    })

        # このシミュレーションのAgentノードとSKILLED_IN
        agents = await graph_client.execute_read(
            "MATCH (a:Agent {simulation_id: $sim_id}) "
            "OPTIONAL MATCH (a)-[r:SKILLED_IN]->(s:Skill) "
            "RETURN a.agent_id AS agent_id, a.name AS name, a.agent_type AS agent_type, "
            "       collect({skill: s.name, proficiency: r.proficiency}) AS skills",
            {"sim_id": job_id},
        )
        for row in agents:
            agent_node_id = f"agent_{row['agent_id'][:8]}"
            elements.append({
                "data": {"id": agent_node_id, "label": row["name"], "type": "Agent"},
            })
            for skill_info in (row["skills"] or []):
                if skill_info.get("skill"):
                    skill_id = f"skill_{skill_info['skill']}"
                    elements.append({
                        "data": {"id": skill_id, "label": skill_info["skill"], "type": "Skill"},
                    })
                    elements.append({
                        "data": {"source": agent_node_id, "target": skill_id, "label": "SKILLED_IN"},
                    })

        # StatRecord（グローバル）
        stats = await graph_client.execute_read(
            "MATCH (sr:StatRecord) "
            "RETURN sr.name AS name, sr.source AS source LIMIT 10"
        )
        for row in stats:
            elements.append({
                "data": {"id": f"stat_{row['name']}", "label": row["name"], "type": "StatRecord"},
            })

        return {"elements": elements}
    finally:
        await graph_client.close()
