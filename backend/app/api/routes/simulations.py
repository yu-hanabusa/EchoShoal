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

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.core.documents.models import DocumentInfo, ParsedDocument, ProcessResult
from app.core.documents.parser import DocumentParseError, DocumentParser
from app.core.documents.processor import DocumentProcessor
from app.core.graph.agent_memory import AgentMemoryStore
from app.core.graph.client import GraphClient
from app.core.graph.rag import GraphRAGRetriever
from app.core.job_manager import JobManager, JobStatus
from app.core.llm.router import LLMRouter
from app.core.redis_client import RedisClient
from app.oasis.simulation_runner import OASISSimulationEngine
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
_running_tasks: dict[str, asyncio.Task[None]] = {}  # job_id → Task


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
        logger.warning("GraphClient初期化失敗")
    return None


# ─── 市場調査（シミュレーション前のデータ収集、非同期ジョブ） ───

@router.post("/research")
async def start_research(
    service_name: str = Form(...),
    service_description: str = Form(default=""),
    description: str = Form(default=""),
    service_url: str = Form(default=""),
    target_year: int = Form(default=0),
    job_id: str = Form(default=""),
) -> JSONResponse:
    """市場調査をバックグラウンドで開始し、job_id を返す.

    既存の job_id が渡された場合はそのジョブを再利用する。
    渡されなかった場合は新規ジョブを作成する。
    フロントエンドは GET /research/{job_id} でポーリングして結果を取得する。
    """
    job_manager = _get_job_manager()

    if job_id:
        info = await job_manager.get_job_info(job_id)
        if info is None:
            raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    else:
        job_id = await job_manager.create_job(
            scenario_description=description[:200] if description else service_description[:200],
            service_name=service_name,
        )

    # フォーム状態をシナリオとして保存（resume 用）
    scenario_data = {
        "description": description or f"{service_name}の市場分析",
        "service_name": service_name,
        "service_url": service_url or None,
        "service_description": service_description,
        "target_year": target_year if target_year >= 2000 else None,
        "num_rounds": 24,
    }
    await job_manager.save_scenario(job_id, scenario_data)

    # 市場調査をバックグラウンドで実行
    task = asyncio.create_task(_run_research_task(job_id, job_manager, scenario_data))
    _running_tasks[job_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(job_id, None))

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "researching"},
    )


@router.get("/{job_id}/research")
async def get_research_result(job_id: str) -> JSONResponse:
    """市場調査の結果を取得する.

    調査中の場合は status: researching を返す。
    完了時は status: completed + 調査結果を返す。
    """
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    research = await job_manager.get_research(job_id)
    if research is None:
        return JSONResponse(
            status_code=200,
            content={"status": "researching", "job_id": job_id},
        )

    if research.get("error"):
        return JSONResponse(
            status_code=200,
            content={"status": "failed", "job_id": job_id, "error": research["error"]},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "completed", "job_id": job_id, "result": research},
    )


async def _run_research_task(
    job_id: str, job_manager: JobManager, scenario_data: dict[str, Any],
) -> None:
    """市場調査をバックグラウンドで実行し、結果を Redis に保存する."""
    try:
        from app.core.market_research.pipeline import run_market_research

        llm = LLMRouter()
        service_name = scenario_data.get("service_name", "")
        description = scenario_data.get("description", "")
        actual_year = scenario_data.get("target_year")

        # シナリオ解析で競合名を推定
        competitors: list[str] = []
        try:
            analyzer = ScenarioAnalyzer(llm=llm)
            scenario = ScenarioInput(
                description=description or f"{service_name}の市場分析",
                service_name=service_name,
            )
            enriched = await analyzer.analyze_async(scenario)
            if enriched.interpolated_info:
                competitors = enriched.interpolated_info.competitors
        except Exception as e:
            logger.warning("競合推定失敗（市場調査は続行）: %s", e)

        result = await run_market_research(
            service_name=service_name,
            description=description or f"{service_name}の市場分析",
            target_year=actual_year,
            competitors=competitors,
            llm=llm,
        )

        await job_manager.save_research(job_id, result.model_dump())
        logger.info("市場調査完了: job=%s", job_id)

    except asyncio.CancelledError:
        logger.info("市場調査キャンセル: job=%s", job_id)
    except Exception as exc:
        logger.exception("市場調査失敗: job=%s", job_id)
        await job_manager.save_research(job_id, {"error": str(exc)})


# ─── メイン: シミュレーション作成 + 即実行 ───

@router.post("/")
async def create_simulation(
    description: str = Form(...),
    num_rounds: int = Form(default=24),
    service_name: str = Form(default=""),
    service_url: str = Form(default=""),
    target_year: int = Form(default=0),
    job_id: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
) -> JSONResponse:
    """シミュレーションを作成し、即座に実行を開始する.

    シナリオテキスト + 文書ファイル（任意、複数可）を同時に受け取る。
    既存の job_id が渡された場合（市場調査済み）はそのジョブを再利用する。
    市場調査結果は Redis から自動取得して知識グラフに格納する。
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
        target_year=target_year if target_year >= 2000 else None,
    )

    job_manager = _get_job_manager()

    # 既存ジョブがあれば再利用、なければ新規作成
    if job_id:
        info = await job_manager.get_job_info(job_id)
        if info is None:
            raise HTTPException(status_code=404, detail="ジョブが見つかりません")
        if info.status != JobStatus.CREATED:
            raise HTTPException(status_code=400, detail="このジョブは既に実行されています")
    else:
        job_id = await job_manager.create_job(
            scenario_description=description[:200],
            service_name=service_name,
        )

    await job_manager.save_scenario(job_id, scenario.model_dump())

    # Redis に保存された市場調査結果をドキュメントとして格納
    graph_client = await _get_graph_client()
    research = await job_manager.get_research(job_id)
    if research and not research.get("error") and graph_client:
        research_docs = [
            ("market_report.txt", research.get("market_report", "")),
            ("user_behavior.txt", research.get("user_behavior", "")),
            ("stakeholders.txt", research.get("stakeholders", "")),
        ]
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        for filename, text in research_docs:
            if text.strip():
                try:
                    doc = ParsedDocument(
                        text=text, filename=filename, source="market_research",
                    )
                    await processor.process(doc)
                    logger.info("市場調査レポート格納: %s → job=%s", filename, job_id)
                except Exception as exc:
                    logger.warning("市場調査レポート格納スキップ: %s - %s", filename, exc)

    # ユーザー文書があればNLP解析→知識グラフに格納
    if graph_client and files:
        parser = DocumentParser()
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        for file in files:
            try:
                content = await file.read()
                doc = parser.parse(content, file.filename or "unknown")
                await processor.process(doc)
                logger.info("文書アップロード完了: %s → job=%s", file.filename, job_id)
            except Exception as exc:
                logger.warning("文書処理スキップ: %s - %s", file.filename, exc)
        await graph_client.close()

    # 即座に実行開始
    await job_manager.set_queued(job_id)
    _active_simulations += 1
    task = asyncio.create_task(_run_simulation_task(job_id, scenario, job_manager))
    _running_tasks[job_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(job_id, None))

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


@router.get("/{job_id}/documents/{doc_id}")
async def get_simulation_document_detail(job_id: str, doc_id: str) -> dict:
    """文書の詳細（要約テキスト含む）を取得する."""
    graph_client = await _get_graph_client()
    if not graph_client:
        raise HTTPException(status_code=503, detail="Graph DB not available")
    try:
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        detail = await processor.get_document_detail(doc_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Document not found")
        return detail
    finally:
        await graph_client.close()


@router.get("/{job_id}/documents/{doc_id}/download")
async def download_document(job_id: str, doc_id: str) -> Response:
    """文書の全文テキストをダウンロードする."""
    graph_client = await _get_graph_client()
    if not graph_client:
        raise HTTPException(status_code=503, detail="Graph DB not available")
    try:
        processor = DocumentProcessor(graph_client, simulation_id=job_id)
        full_text = await processor.get_document_full_text(doc_id)
        if full_text is None:
            raise HTTPException(status_code=404, detail="Document not found")
        # ファイル名を取得
        detail = await processor.get_document_detail(doc_id)
        filename = detail["filename"] if detail else f"{doc_id}.txt"
        return Response(
            content=full_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
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
        service_name=scenario.service_name,
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
    task = asyncio.create_task(_run_simulation_task(new_job_id, scenario, job_manager))
    _running_tasks[new_job_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(new_job_id, None))

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
        logger.warning("グラフコンポーネント初期化失敗: simulation_id=%s", simulation_id)
        return None, None, None


async def _run_simulation_task(
    job_id: str, scenario: ScenarioInput, job_manager: JobManager
) -> None:
    global _active_simulations
    graph_client: GraphClient | None = None
    try:
        await job_manager.set_running(job_id)

        # 全体ステップ: 準備4 + シミュレーションN + レポート1 = N+5
        total_steps = scenario.num_rounds + 5
        step = 0

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="シナリオ解析中")

        llm = LLMRouter()

        analyzer = ScenarioAnalyzer(llm=llm)
        enriched = await analyzer.analyze_async(scenario)
        logger.info(
            "シナリオ解析: ディメンション%d件, ステークホルダー%d件",
            len(enriched.detected_dimensions), len(enriched.detected_stakeholders),
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

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="エージェント生成中")
        generator = AgentGenerator(llm)
        agents = await generator.generate(scenario, enriched, doc_entities)

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="イベントスケジュール生成中")
        event_scheduler = EventScheduler(llm=llm)
        await event_scheduler.generate_from_scenario(scenario)

        step += 1
        await job_manager.update_progress(job_id, step, total_steps, phase="市場初期状態をLLMが推定中")

        async def on_progress(current: int, total: int) -> None:
            await job_manager.update_progress(
                job_id, step + current, total_steps,
                phase=f"{current}ヶ月目をシミュレーション中（{total}ヶ月中）",
            )

        oasis_engine = OASISSimulationEngine(
            agents=agents, llm=llm, scenario=scenario,
            on_progress=on_progress, event_scheduler=event_scheduler,
            enriched_scenario=enriched,
            simulation_id=job_id,
            rag=rag, agent_memory=agent_memory,
        )
        engine = oasis_engine

        results = await engine.run()

        # レポートをシミュレーション結果と一緒に生成・保存
        await job_manager.update_progress(job_id, total_steps - 1, total_steps, phase="レポート生成中")
        report_dict = None
        try:
            from app.reports.extractor import build_report_data
            from app.reports.generator import ReportGenerator
            report_input = build_report_data(
                rounds=results,
                scenario_description=scenario.description,
                agents_summary=engine.get_summary().get("agents", []),
                confidence_notes=(
                    enriched.interpolated_info.confidence_notes
                    if enriched and enriched.interpolated_info else None
                ),
            )
            report_generator = ReportGenerator(llm=llm)
            report = await report_generator.generate(report_input)
            report_dict = report.model_dump()
            logger.info("レポート生成完了: job=%s", job_id)
        except Exception:
            logger.warning("レポート生成失敗（結果は保存します）: job=%s", job_id)

        result_data = {
            "scenario": scenario.model_dump(),
            "summary": engine.get_summary(),
            "rounds": [r.model_dump() for r in results],
            "report": report_dict,
        }

        # OASISエンジンの場合: ソーシャルフィードとグラフ同期
        if oasis_engine is not None:
            try:
                result_data["social_feed"] = oasis_engine.get_social_feed()
            except Exception:
                logger.warning("OASISソーシャルフィード取得失敗: job=%s", job_id)

            # OASIS → Neo4j グラフ同期
            if graph_client and agent_memory:
                try:
                    from app.oasis.graph_sync import sync_oasis_to_neo4j
                    from app.oasis.config import get_database_path

                    # OASIS agent_id → EchoShoal agent_id マッピング構築
                    oasis_id_map = {}
                    for i, agent in enumerate(agents):
                        oasis_id_map[i] = agent.id

                    sync_result = await sync_oasis_to_neo4j(
                        db_path=get_database_path(job_id),
                        graph_client=graph_client,
                        simulation_id=job_id,
                        agent_id_map=oasis_id_map,
                    )
                    logger.info(
                        "OASISグラフ同期完了: %dエッジ同期 (%dエラー)",
                        sync_result.edges_synced, sync_result.errors,
                    )
                except Exception:
                    logger.warning("OASISグラフ同期失敗: job=%s", job_id)

        await job_manager.set_completed(job_id, result_data)

    except asyncio.CancelledError:
        logger.info("シミュレーションキャンセル: job=%s", job_id)
        await job_manager.set_failed(job_id, "キャンセルされました")
    except Exception as exc:
        logger.exception("シミュレーション失敗: job=%s", job_id)
        await job_manager.set_failed(job_id, str(exc))
    finally:
        _active_simulations -= 1
        if graph_client:
            try:
                await graph_client.close()
            except Exception:
                logger.debug("GraphClient close失敗（シミュレーション終了処理中）")


# ─── 結果取得 ───

@router.get("/")
async def list_simulations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """過去のシミュレーション一覧を取得する（ページネーション対応）."""
    job_manager = _get_job_manager()
    jobs, total = await job_manager.list_jobs(skip=skip, limit=limit)
    return {
        "items": [j.model_dump() for j in jobs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


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
    # CREATED 状態のジョブにはシナリオ情報を含める（resume 用）
    if info.status == JobStatus.CREATED:
        scenario = await job_manager.get_scenario(job_id)
        if scenario:
            response["scenario"] = scenario
    return response


@router.get("/{job_id}/progress")
async def get_simulation_progress(job_id: str) -> dict[str, Any]:
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return {"job_id": job_id, "status": info.status.value, "progress": info.progress}


# ─── シナリオ名更新 ───

@router.patch("/{job_id}")
async def update_simulation(job_id: str, body: dict[str, Any]) -> dict[str, str]:
    """シナリオ名を更新する."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    scenario_name = body.get("scenario_name")
    if scenario_name is None:
        raise HTTPException(status_code=400, detail="scenario_name は必須です")
    await job_manager.update_scenario_name(job_id, str(scenario_name))
    return {"status": "updated", "job_id": job_id}


# ─── 削除 ───

@router.delete("/{job_id}")
async def delete_simulation(job_id: str) -> dict[str, str]:
    """シミュレーションを削除する（実行中タスク停止 + Redis + Neo4jクリーンアップ）."""
    job_manager = _get_job_manager()
    info = await job_manager.get_job_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    # 実行中のバックグラウンドタスクをキャンセル
    task = _running_tasks.pop(job_id, None)
    if task and not task.done():
        task.cancel()
        logger.info("バックグラウンドタスクをキャンセル: job=%s", job_id)

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
