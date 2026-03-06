"""
Entity Graph API routes — FastAPI router for graph operations.

All endpoints are registered under /api/v1/entity-graph and tagged
"Entity Graph" in the auto-generated /docs.

Endpoints:
  POST /api/v1/entity-graph/build             → build graph + fraud detect + export
  GET  /api/v1/entity-graph/{job_id}           → graph export for frontend
  GET  /api/v1/entity-graph/{job_id}/fraud-flags → fraud detection results
  POST /api/v1/entity-graph/{job_id}/set-decision → write decision back to Neo4j
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from deep_learning.schemas import EntityExtraction
from .schemas import (
    BuildGraphRequest,
    SetDecisionRequest,
    FraudFlag,
    GraphNode,
    GraphEdge,
)
from .neo4j_client import get_driver, APPLICATION
from .graph_writer import write_entity_graph
from .fraud_detector import run_all_fraud_checks
from .graph_exporter import export_graph_for_ui

from utils import validate_job_id

logger = logging.getLogger("entity_graph.routes")

# Shared volume base path
_BASE_PATH = Path("/tmp/intelli-credit")

router = APIRouter(
    prefix="/api/v1/entity-graph",
    tags=["Entity Graph"],
)


# =============================================================================
# Response models (route-specific, not in schemas.py)
# =============================================================================


class BuildGraphResponse(BaseModel):
    """Immediate response from POST /build."""

    model_config = {"json_schema_extra": {"title": "BuildGraphResponse"}}

    status: Literal["processing"] = Field(
        default="processing", description="Always 'processing' — runs in background"
    )
    job_id: str = Field(..., description="Echo of the job_id")
    message: str = Field(
        default="Entity graph build queued",
        description="Human-readable status message",
    )


class GraphStatusResponse(BaseModel):
    """GET /api/v1/entity-graph/{job_id} response."""

    model_config = {"json_schema_extra": {"title": "GraphStatusResponse"}}

    status: Literal["ready", "processing", "failed"] = Field(
        ..., description="Current status of the graph export"
    )
    job_id: str = Field(..., description="Job ID")
    nodes: List[GraphNode] = Field(
        default_factory=list, description="Graph nodes (empty if not ready)"
    )
    edges: List[GraphEdge] = Field(
        default_factory=list, description="Graph edges (empty if not ready)"
    )
    node_count: int = Field(default=0, description="Total number of nodes")
    edge_count: int = Field(default=0, description="Total number of edges")
    error: Optional[str] = Field(
        default=None, description="Error message if status is 'failed'"
    )


class FraudFlagsResponse(BaseModel):
    """GET /api/v1/entity-graph/{job_id}/fraud-flags response."""

    model_config = {"json_schema_extra": {"title": "FraudFlagsResponse"}}

    status: Literal["ready", "processing", "failed"] = Field(
        ..., description="Current status of fraud detection"
    )
    job_id: str = Field(..., description="Job ID")
    flags: List[FraudFlag] = Field(
        default_factory=list, description="Detected fraud flags"
    )
    total_score_penalty: int = Field(
        default=0, description="Sum of all flag score penalties"
    )
    highest_severity: str = Field(
        default="NONE", description="Highest severity across all flags"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if status is 'failed'"
    )

class SetDecisionResponse(BaseModel):
    """POST /api/v1/entity-graph/{job_id}/set-decision response."""

    model_config = {"json_schema_extra": {"title": "SetDecisionResponse"}}

    status: Literal["updated"] = Field(
        default="updated", description="Always 'updated' on success"
    )
    job_id: str = Field(..., description="Job ID")


# =============================================================================
# Background task: build graph pipeline
# =============================================================================

async def _build_graph_pipeline(
    job_id: str,
    borrower_name: str,
    entity_extraction_path: str,
):
    """
    Background task: read EntityExtraction → write graph → fraud detect → export.

    Steps:
      1. Read EntityExtraction from ocr_output.json
      2. write_entity_graph()
      3. run_all_fraud_checks() → writes entity_fraud_flags.json
      4. export_graph_for_ui() → writes entity_graph.json
    """
    try:
        # 1. Read EntityExtraction from ocr_output.json
        logger.info(f"[{job_id}] Graph build step 1/4 — Reading entity extraction")
        extraction_path = Path(entity_extraction_path)
        if not extraction_path.exists():
            raise FileNotFoundError(
                f"Entity extraction file not found: {entity_extraction_path}"
            )

        raw = json.loads(extraction_path.read_text(encoding="utf-8"))

        # Extract entity_extraction from ocr_output.json
        entity_data_raw = raw.get("entity_extraction")
        if entity_data_raw is None:
            logger.warning(
                f"[{job_id}] No entity_extraction in {entity_extraction_path}. "
                f"Skipping graph build."
            )
            return

        entity_data = EntityExtraction(**entity_data_raw)

        # 2. Write entity graph to Neo4j
        logger.info(f"[{job_id}] Graph build step 2/4 — Writing entities to Neo4j")
        write_result = await write_entity_graph(entity_data, job_id)
        logger.info(
            f"[{job_id}] Graph write: {write_result.nodes_written} nodes, "
            f"{write_result.relationships_written} rels, "
            f"status={write_result.status}"
        )

        # 3. Fraud detection
        logger.info(f"[{job_id}] Graph build step 3/4 — Running fraud checks")
        driver = get_driver()
        fraud_result = await run_all_fraud_checks(driver, job_id, borrower_name)
        logger.info(
            f"[{job_id}] Fraud detection: {len(fraud_result.flags)} flags, "
            f"penalty={fraud_result.total_score_penalty}"
        )

        # 4. Export graph for frontend
        logger.info(f"[{job_id}] Graph build step 4/4 — Exporting graph JSON")
        export = await export_graph_for_ui(driver, job_id, borrower_name)
        logger.info(
            f"[{job_id}] ✅ Graph build complete: "
            f"{len(export.nodes)} nodes, {len(export.edges)} edges"
        )

    except Exception as e:
        logger.error(f"[{job_id}] ❌ Graph build failed: {e}")
        # Write an error marker so the GET endpoint can report failure
        error_file = _BASE_PATH / job_id / "entity_graph_error.json"
        error_file.parent.mkdir(parents=True, exist_ok=True)
        error_file.write_text(
            json.dumps({"status": "failed", "error": "Graph build failed"}),
            encoding="utf-8",
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/build", response_model=BuildGraphResponse)
async def build_entity_graph(
    request: BuildGraphRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger entity graph build: write entities to Neo4j, run fraud detection,
    and export graph JSON for the frontend. Runs in the background.
    """
    background_tasks.add_task(
        _build_graph_pipeline,
        job_id=request.job_id,
        borrower_name=request.borrower_name,
        entity_extraction_path=request.entity_extraction_path,
    )

    return BuildGraphResponse(
        status="processing",
        job_id=request.job_id,
        message="Entity graph build queued",
    )


@router.get("/{job_id}", response_model=GraphStatusResponse)
async def get_entity_graph(job_id: str):
    """
    Return the graph export JSON for the frontend force-directed visualization.
    Reads from /tmp/intelli-credit/{job_id}/entity_graph.json.
    """
    validate_job_id(job_id)
    graph_file = _BASE_PATH / job_id / "entity_graph.json"
    error_file = _BASE_PATH / job_id / "entity_graph_error.json"

    # Check for error
    if error_file.exists():
        try:
            err = json.loads(error_file.read_text(encoding="utf-8"))
            return GraphStatusResponse(
                status="failed",
                job_id=job_id,
                error=err.get("error", "Unknown error"),
            )
        except Exception:
            return GraphStatusResponse(
                status="failed",
                job_id=job_id,
                error="Graph build failed (could not read error details)",
            )

    # Check if graph exists
    if not graph_file.exists():
        return GraphStatusResponse(
            status="processing",
            job_id=job_id,
        )

    try:
        data = json.loads(graph_file.read_text(encoding="utf-8"))
        nodes = [GraphNode(**n) for n in data.get("nodes", [])]
        edges = [GraphEdge(**e) for e in data.get("edges", [])]
        return GraphStatusResponse(
            status="ready",
            job_id=job_id,
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
        )
    except Exception as e:
        logger.error(f"Failed to read graph export for {job_id}: {e}")
        return GraphStatusResponse(
            status="failed",
            job_id=job_id,
            error="Failed to read graph export",
        )


@router.get("/{job_id}/fraud-flags", response_model=FraudFlagsResponse)
async def get_fraud_flags(job_id: str):
    """
    Return fraud detection results for the ML scoring pipeline and UI dashboard.
    Reads from /tmp/intelli-credit/{job_id}/entity_fraud_flags.json.
    """
    validate_job_id(job_id)
    fraud_file = _BASE_PATH / job_id / "entity_fraud_flags.json"

    if not fraud_file.exists():
        return FraudFlagsResponse(
            status="processing",
            job_id=job_id,
        )

    try:
        data = json.loads(fraud_file.read_text(encoding="utf-8"))
        flags = [FraudFlag(**f) for f in data.get("flags", [])]
        return FraudFlagsResponse(
            status="ready",
            job_id=job_id,
            flags=flags,
            total_score_penalty=data.get("total_score_penalty", 0),
            highest_severity=data.get("highest_severity", "NONE"),
        )
    except Exception as e:
        logger.error(f"Failed to read fraud flags for {job_id}: {e}")
        return FraudFlagsResponse(
            status="failed",
            job_id=job_id,
            error=str(e),
        )


@router.post("/{job_id}/set-decision", response_model=SetDecisionResponse)
async def set_decision(job_id: str, request: SetDecisionRequest):
    """
    Write the final credit decision back into the APPLICATION node in Neo4j.
    Enables historical rejection detection for future applications.
    """
    import asyncio

    try:
        driver = get_driver()

        def _write_decision():
            with driver.session() as session:
                session.run(
                    f"MATCH (a:{APPLICATION} {{job_id: $job_id}}) "
                    f"SET a.decision = $decision, "
                    f"    a.score = $score, "
                    f"    a.decided_at = datetime()",
                    job_id=job_id,
                    decision=request.decision,
                    score=request.score,
                )

        await asyncio.to_thread(_write_decision)

        logger.info(
            f"[{job_id}] Decision set: {request.decision} (score={request.score})"
        )

        return SetDecisionResponse(status="updated", job_id=job_id)

    except Exception as e:
        logger.error(f"[{job_id}] Failed to set decision: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write decision to Neo4j: {e}",
        )
