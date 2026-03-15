"""シミュレーション API エンドポイント.

フロー:
  POST /api/simulations/  → シナリオ + 文書を同時に受け取り、即座に実行開始
  POST /api/simulations/{id}/documents  → 追加文書アップロード（再シミュレーション用）
  POST /api/simulations/{id}/rerun  → 追加文書を含めて再実行

すべてのデータは job_id (= simulation_id) でスコープされる。
"""

from __future__ import annotations

import asyncio
import json
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
from app.simulation.agent_generator import AgentGenerator
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
    try:
        client = GraphClient()
        if await client.is_available():
            return client
    except Exception:
        pass
    return None


# ─── メイン: シミュレーション作成 + 即実行 ───

@router.post("/")
async def create_simulation(
    description: str = Form(...),
    num_rounds: int = Form(default=24),
    service_name: str = Form(default=""),
    service_url: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
) -> JSONResponse:
    """シミュレーションを作成し、即座に実行を開始する.

    シナリオテキスト + 文書ファイル（任意、複数可）を同時に受け取る。
    AI加速度・経済ショック等のパラメータはNLPから自動推定する。
    """
    global _active_simulations
    _check_rate_limit()

    if len(description) < 10:
        raise HTTPException(status_code=400, detail="シナリオは10文字以上で入力してください")

    # ScenarioInput作成（パラメータは自動推定されるので0で初期化）
    scenario = ScenarioInput(
        description=description,
        num_rounds=min(num_rounds, settings.max_rounds),
        service_name=service_name,
        service_url=service_url or None,
    )

    job_manager = _get_job_manager()
    job_id = await job_manager.create_job(
        scenario_description=description[:200],
    )
    await job_manager.save_scenario(job_id, scenario.model_dump())

    # 文書があればNLP解析→知識グラフに格納
    graph_client = await _get_graph_client()
    if graph_client and files:
        parser = DocumentParser()
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        for file in files:
            try:
                content = await file.read()
                doc = parser.parse(content, file.filename or "unknown")
                await processor.process(doc)
                logger.info("文書アップロード完了: %s → job=%s", file.filename, job_id)
            except (DocumentParseError, Exception) as exc:
                logger.warning("文書処理スキップ: %s - %s", file.filename, exc)
        await graph_client.close()

    # 即座に実行開始
    await job_manager.set_queued(job_id)
    _active_simulations += 1
    asyncio.create_task(_run_simulation_task(job_id, scenario, job_manager))

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "queued"},
    )


# ─── 追加文書アップロード（結果を見た後に追加→再実行用） ───

@router.post("/{job_id}/documents", response_model=ProcessResult)
async def upload_additional_document(
    job_id: str,
    file: UploadFile = File(...),
    source: str = Form(default=""),
) -> ProcessResult:
    """完了済みシミュレーションに追加文書をアップロードする.

    アップロード後に /rerun で再シミュレーション可能。
    """
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

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
    """このシミュレーションの文書一覧を取得する."""
    graph_client = await _get_graph_client()
    if not graph_client:
        return []
    try:
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        return await processor.get_documents()
    finally:
        await graph_client.close()


# ─── 再シミュレーション ───

@router.post("/{job_id}/rerun")
async def rerun_simulation(job_id: str) -> JSONResponse:
    """追加文書を含めてシミュレーションを再実行する.

    新しいjob_idが発行され、元のjob_idの文書データを引き継ぐ。
    """
    global _active_simulations
    _check_rate_limit()

    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="元のジョブが見つかりません")

    scenario_data = await job_manager.get_scenario(job_id)
    if not scenario_data:
        raise HTTPException(status_code=400, detail="シナリオが保存されていません")

    scenario = ScenarioInput(**scenario_data)

    # 新しいジョブを作成（文書はNeo4jで同じsimulation_id=job_idを参照）
    new_job_id = await job_manager.create_job(
        scenario_description=scenario.description[:200],
    )
    await job_manager.save_scenario(new_job_id, scenario_data)

    # 元のジョブの文書をコピー（simulation_idを新しいジョブに紐付け）
    graph_client = await _get_graph_client()
    if graph_client:
        try:
            await graph_client.execute_write(
                "MATCH (d:Document {simulation_id: $old_id}) "
                "WITH d, d.doc_id + '-' + $new_id AS new_doc_id "
                "CREATE (d2:Document) SET d2 = properties(d), "
                "       d2.doc_id = new_doc_id, d2.simulation_id = $new_id "
                "WITH d2, d "
                "OPTIONAL MATCH (d)-[:MENTIONS]->(e) "
                "FOREACH (ent IN CASE WHEN e IS NOT NULL THEN [e] ELSE [] END | "
                "  CREATE (d2)-[:MENTIONS]->(ent))",
                {"old_id": job_id, "new_id": new_job_id},
            )
        except Exception:
            logger.warning("文書コピー失敗: %s → %s", job_id, new_job_id)
        finally:
            await graph_client.close()

    await job_manager.set_queued(new_job_id)
    _active_simulations += 1
    asyncio.create_task(_run_simulation_task(new_job_id, scenario, job_manager))

    return JSONResponse(
        status_code=202,
        content={"job_id": new_job_id, "status": "queued", "parent_job_id": job_id},
    )


# ─── シミュレーション実行（バックグラウンド） ───

async def _setup_graph_components(
    simulation_id: str,
) -> tuple[GraphRAGRetriever | None, AgentMemoryStore | None, GraphClient | None]:
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
    global _active_simulations
    graph_client: GraphClient | None = None
    try:
        await job_manager.set_running(job_id)

        llm = LLMRouter()

        analyzer = ScenarioAnalyzer(llm=llm)
        enriched = await analyzer.analyze_async(scenario)
        logger.info(
            "シナリオ解析: ディメンション%d件, ステークホルダー%d件, 経済環境%.1f, 技術破壊度%.1f",
            len(enriched.detected_dimensions), len(enriched.detected_stakeholders),
            scenario.economic_climate, scenario.tech_disruption,
        )

        # 知識グラフコンポーネント
        rag, agent_memory, graph_client = await _setup_graph_components(job_id)

        # GitHub README自動取得
        if scenario.service_url and graph_client:
            from app.core.documents.fetcher import fetch_github_readme, is_github_url
            if is_github_url(scenario.service_url):
                try:
                    readme_content = await fetch_github_readme(scenario.service_url)
                    if readme_content:
                        parser = DocumentParser()
                        doc = parser.parse(
                            readme_content.encode("utf-8"),
                            f"README-{scenario.service_name or 'service'}.md",
                            source=scenario.service_url,
                        )
                        from app.core.documents.processor import DocumentProcessor
                        proc = DocumentProcessor(graph_client, simulation_id=job_id)
                        await proc.process(doc)
                        logger.info("GitHub README取得・処理完了: %s", scenario.service_url)
                except Exception:
                    logger.warning("GitHub README処理失敗: %s", scenario.service_url)

        # 文書エンティティ取得 → エージェント動的生成
        doc_entities: dict[str, list[str]] | None = None
        if graph_client:
            try:
                from app.core.documents.processor import DocumentProcessor
                proc = DocumentProcessor(graph_client, simulation_id=job_id)
                doc_entities = await proc.get_document_entities()
            except Exception:
                logger.warning("文書エンティティ取得失敗")

        generator = AgentGenerator(llm)
        agents = await generator.generate(scenario, enriched, doc_entities)

        event_scheduler = EventScheduler(llm=llm)
        await event_scheduler.generate_from_scenario(scenario)

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
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return {"job_id": job_id, "status": info.status.value, "progress": info.progress}


# ─── 削除 ───

@router.delete("/{job_id}")
async def delete_simulation(job_id: str) -> dict[str, str]:
    """シミュレーションを削除する（Redis + Neo4jのデータをクリーンアップ）."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    # Redis削除
    await job_manager.delete_job(job_id)

    # Neo4j削除（このシミュレーションのデータ）
    graph_client = await _get_graph_client()
    if graph_client:
        try:
            await graph_client.execute_write(
                "MATCH (n) WHERE n.simulation_id = $sim_id DETACH DELETE n",
                {"sim_id": job_id},
            )
        except Exception:
            logger.warning("Neo4jデータ削除失敗: %s", job_id)
        finally:
            await graph_client.close()

    return {"status": "deleted", "job_id": job_id}


# ─── グラフ可視化（シミュレーションスコープ） ───

@router.get("/{job_id}/graph")
async def get_simulation_graph(job_id: str) -> dict[str, Any]:
    graph_client = await _get_graph_client()
    if not graph_client:
        return {"elements": []}
    try:
        elements: list[dict[str, Any]] = []

        # Documents + MENTIONS
        docs = await graph_client.execute_read(
            "MATCH (d:Document {simulation_id: $sim_id}) "
            "OPTIONAL MATCH (d)-[:MENTIONS]->(e) "
            "RETURN d.doc_id AS doc_id, d.filename AS filename, "
            "       collect({name: e.name, type: labels(e)[0]}) AS mentions",
            {"sim_id": job_id},
        )
        for row in docs:
            doc_id = f"doc_{row['doc_id']}"
            elements.append({"data": {"id": doc_id, "label": row["filename"], "type": "Document"}})
            for m in (row["mentions"] or []):
                if m.get("name"):
                    prefix = {"Skill": "skill_", "Company": "company_", "Policy": "policy_"}.get(m.get("type", ""), "")
                    tid = f"{prefix}{m['name']}"
                    elements.append({"data": {"id": tid, "label": m["name"], "type": m.get("type", "Unknown")}})
                    elements.append({"data": {"source": doc_id, "target": tid, "label": "MENTIONS"}})

        # Agents + SKILLED_IN
        agents = await graph_client.execute_read(
            "MATCH (a:Agent {simulation_id: $sim_id}) "
            "OPTIONAL MATCH (a)-[r:SKILLED_IN]->(s:Skill) "
            "RETURN a.agent_id AS agent_id, a.name AS name, "
            "       collect({skill: s.name, proficiency: r.proficiency}) AS skills",
            {"sim_id": job_id},
        )
        for row in agents:
            aid = f"agent_{row['agent_id'][:8]}"
            elements.append({"data": {"id": aid, "label": row["name"], "type": "Agent"}})
            for s in (row["skills"] or []):
                if s.get("skill"):
                    sid = f"skill_{s['skill']}"
                    elements.append({"data": {"id": sid, "label": s["skill"], "type": "Skill"}})
                    elements.append({"data": {"source": aid, "target": sid, "label": "SKILLED_IN"}})

        return {"elements": elements}
    finally:
        await graph_client.close()
