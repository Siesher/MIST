"""Knowledge Forge API — active knowledge graph, not RAG.

Endpoints expose the graph stored in data/knowledge/forge.json and let
users upload source documents which the LLM extracts into nodes/edges.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.auth import get_optional_user
from backend.app.models.database import get_db
from backend.app.models.tables import SourceTable, UserTable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Lazy-loaded graph to avoid heavy imports during API startup
_graph = None


def _owns(row: SourceTable, user: UserTable | None) -> bool:
    """Доступ к источнику: владелец или legacy-публичный (user_id IS NULL)."""
    if row.user_id is None:
        return True
    return user is not None and row.user_id == user.id


def get_graph():
    """Load KnowledgeGraph singleton from data/knowledge/forge.json."""
    global _graph
    if _graph is None:
        from src.knowledge.knowledge_forge import KnowledgeGraph

        forge_path = Path("data/knowledge/forge.json")
        _graph = KnowledgeGraph(storage_path=forge_path)
    return _graph


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    domains: dict[str, int]
    types: dict[str, int]


class NodeSummary(BaseModel):
    id: str
    title: str
    title_en: str | None = None
    type: str
    domain: str
    difficulty: float
    confidence: float


class NodeDetail(NodeSummary):
    content: str
    tags: list[str]
    neighbors: dict[str, list[dict[str, Any]]]


class CreateNodeRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    title_en: str | None = None
    domain: str = Field(default="math", pattern="^(math|physics|chemistry|biology|cs|other)$")
    node_type: str = Field(
        default="concept",
        pattern="^(concept|formula|theorem|example|method|misconception)$",
    )
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    content: str = ""


class SourceCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=20)
    kind: str = Field(default="text", pattern="^(text|notes|url|pdf)$")
    domain: str = Field(default="math", pattern="^(math|physics|chemistry|biology|cs|other)$")


class SourceInfo(BaseModel):
    id: str
    title: str
    kind: str
    domain: str
    status: str
    error: str | None
    nodes_extracted: int
    edges_extracted: int
    created_at: datetime
    extracted_at: datetime | None
    preview: str


class SourceList(BaseModel):
    sources: list[SourceInfo]
    total: int


# ─────────────────────────────────────────────────────────────────────
# Graph endpoints
# ─────────────────────────────────────────────────────────────────────


@router.post("/nodes", response_model=NodeSummary, status_code=status.HTTP_201_CREATED)
async def create_node(req: CreateNodeRequest):
    """Manually add a node to the Knowledge Forge graph (the «+ тема» button)."""
    import re
    import uuid

    from src.knowledge.knowledge_forge import KnowledgeNode, NodeType

    g = get_graph()
    base = (req.title_en or req.title).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", base).strip("_")[:40] or uuid.uuid4().hex[:8]
    node_id = f"{req.domain}:{slug}:{req.node_type}"
    if g.get_node(node_id) is not None:
        node_id = f"{node_id}:{uuid.uuid4().hex[:4]}"
    node = KnowledgeNode(
        id=node_id,
        node_type=NodeType(req.node_type),
        title=req.title,
        title_en=req.title_en or req.title,
        content=req.content,
        domain=req.domain,
        difficulty=req.difficulty,
        source="manual_add",
    )
    g.add_node(node)
    g.save()
    logger.info("Forge node added manually: %s", node_id)
    return NodeSummary(
        id=node.id,
        title=node.title,
        title_en=node.title_en,
        type=node.node_type.value,
        domain=node.domain,
        difficulty=node.difficulty,
        confidence=node.confidence,
    )


@router.get("/stats", response_model=GraphStats)
async def get_stats():
    """Total nodes/edges + histograms by domain and type."""
    g = get_graph()
    domains: dict[str, int] = {}
    types: dict[str, int] = {}
    for node in g._nodes.values():  # noqa: SLF001
        domains[node.domain] = domains.get(node.domain, 0) + 1
        types[node.node_type.value] = types.get(node.node_type.value, 0) + 1
    return GraphStats(
        total_nodes=len(g._nodes),
        total_edges=len(g._edges),
        domains=domains,
        types=types,
    )


@router.get("/nodes", response_model=list[NodeSummary])
async def list_nodes(
    domain: str | None = None,
    type: str | None = None,
    q: str | None = None,
    limit: int = 100,
):
    """List graph nodes with filters."""
    g = get_graph()
    nodes = list(g._nodes.values())  # noqa: SLF001
    if domain:
        nodes = [n for n in nodes if n.domain == domain]
    if type:
        nodes = [n for n in nodes if n.node_type.value == type]
    if q:
        ql = q.lower()
        nodes = [n for n in nodes if ql in n.title.lower() or ql in (n.title_en or "").lower()]
    return [
        NodeSummary(
            id=n.id,
            title=n.title,
            title_en=n.title_en,
            type=n.node_type.value,
            domain=n.domain,
            difficulty=n.difficulty,
            confidence=n.confidence,
        )
        for n in nodes[:limit]
    ]


@router.get("/nodes/{node_id}", response_model=NodeDetail)
async def get_node(node_id: str):
    """Node detail with categorized neighbors."""
    g = get_graph()
    node = g.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node not found: {node_id}")
    explored = g.explore(node_id) or {}
    return NodeDetail(
        id=node.id,
        title=node.title,
        title_en=node.title_en,
        type=node.node_type.value,
        domain=node.domain,
        difficulty=node.difficulty,
        confidence=node.confidence,
        content=node.content,
        tags=list(node.tags),
        neighbors=explored.get("neighbors", {}),
    )


# ─────────────────────────────────────────────────────────────────────
# Source upload + extraction
# ─────────────────────────────────────────────────────────────────────


async def _run_extraction(source_id: str) -> None:
    """Background task: extract knowledge from source text via LLM."""
    from backend.app.models.database import async_session_factory
    from src.knowledge.source_extractor import SourceExtractor

    async with async_session_factory() as db:
        src_row = await db.get(SourceTable, source_id)
        if not src_row:
            return
        src_row.status = "extracting"
        await db.commit()

        try:
            logger.info(f"Extraction started: {src_row.title}")
            graph = get_graph()
            # llm_client=None → SourceExtractor сам выберет живой бэкенд (llama-swap
            # через _make_llm), а не жёстко Ollama LLMClient (который может быть не
            # запущен). Иначе извлечение по API-пути молча падает.
            extractor = SourceExtractor()

            def _sync_extract():
                return extractor.extract(
                    text=src_row.content,
                    domain=src_row.domain,
                    source_name=src_row.title,
                )

            loop = asyncio.get_event_loop()
            nodes, edges = await loop.run_in_executor(None, _sync_extract)

            # Actually add extracted nodes/edges to the graph
            added_nodes = 0
            for node in nodes:
                if graph.get_node(node.id) is None:
                    graph.add_node(node)
                    added_nodes += 1

            added_edges = 0
            for edge in edges:
                try:
                    if not graph.has_edge(edge.source_id, edge.target_id, edge.edge_type):
                        graph.add_edge(edge)
                        added_edges += 1
                except KeyError:
                    # Edge references a node that wasn't extracted — skip
                    continue

            # Persist the updated graph to disk
            graph.save()

            src_row.status = "extracted"
            src_row.nodes_extracted = added_nodes
            src_row.edges_extracted = added_edges
            src_row.extracted_at = datetime.utcnow()
            logger.info(f"Extraction done: {src_row.title} — +{added_nodes}n +{added_edges}e")
        except Exception as e:
            logger.exception(f"Extraction failed: {e}")
            src_row.status = "failed"
            src_row.error = str(e)[:500]
        finally:
            await db.commit()


@router.post("/sources", response_model=SourceInfo, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    """Upload a source; trigger extraction in background."""
    row = SourceTable(
        title=payload.title,
        kind=payload.kind,
        domain=payload.domain,
        content=payload.content,
        status="pending",
        user_id=user.id if user else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    bg.add_task(_run_extraction, row.id)

    return _to_info(row)


@router.get("/sources", response_model=SourceList)
async def list_sources(
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    """List sources owned by the current user (plus legacy public ones)."""
    q = select(SourceTable).order_by(SourceTable.created_at.desc())
    if user:
        q = q.where(or_(SourceTable.user_id == user.id, SourceTable.user_id.is_(None)))
    else:
        q = q.where(SourceTable.user_id.is_(None))
    rows = list((await db.execute(q)).scalars())
    return SourceList(sources=[_to_info(r) for r in rows], total=len(rows))


@router.get("/sources/{source_id}", response_model=SourceInfo)
async def get_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    row = await db.get(SourceTable, source_id)
    if not row or not _owns(row, user):
        raise HTTPException(404, "Source not found")
    return _to_info(row)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    row = await db.get(SourceTable, source_id)
    if not row or not _owns(row, user):
        raise HTTPException(404, "Source not found")
    await db.delete(row)
    await db.commit()


# ─────────────────────────────────────────────────────────────────────
# Living KG: auto-evolution proposals
# ─────────────────────────────────────────────────────────────────────


class ProposalInfo(BaseModel):
    key: str
    kind: str
    confidence: float
    payload: dict[str, Any]
    evidence: list[dict[str, Any]]
    reasoning: str | None = None


class EvolutionSummary(BaseModel):
    sessions_analyzed: int
    proposals_generated: int
    proposals_accepted: int
    proposals_rejected: int
    pending: int
    last_sweep_at: float
    last_sweep_stats: dict[str, int]


@router.get("/evolution/summary", response_model=EvolutionSummary)
async def get_evolution_summary() -> EvolutionSummary:
    """Stats: sessions analyzed, proposals generated/accepted/rejected, pending."""
    from backend.app.services.kg_evolution_service import get_kg_evolution

    return EvolutionSummary(**get_kg_evolution().summary())


@router.get("/proposals", response_model=list[ProposalInfo])
async def list_proposals() -> list[ProposalInfo]:
    """All pending graph proposals awaiting review."""
    from backend.app.services.kg_evolution_service import get_kg_evolution

    items = get_kg_evolution().list_proposals()
    result = []
    for p in items:
        kind = p.get("kind")
        if hasattr(kind, "value"):
            kind = kind.value
        result.append(
            ProposalInfo(
                key=f"{kind}:{p.get('payload', {}).get('id', '?')}",
                kind=str(kind),
                confidence=p.get("confidence", 0.0),
                payload=p.get("payload", {}),
                evidence=p.get("evidence", []),
                reasoning=p.get("reasoning"),
            )
        )
    return result


@router.post("/proposals/{proposal_key}/accept")
async def accept_proposal(proposal_key: str) -> dict[str, bool]:
    from backend.app.services.kg_evolution_service import get_kg_evolution

    ok = get_kg_evolution().manual_decision(proposal_key, accept=True)
    if not ok:
        raise HTTPException(404, f"Proposal not found: {proposal_key}")
    return {"accepted": True}


@router.post("/proposals/{proposal_key}/reject")
async def reject_proposal(proposal_key: str) -> dict[str, bool]:
    from backend.app.services.kg_evolution_service import get_kg_evolution

    ok = get_kg_evolution().manual_decision(proposal_key, accept=False)
    if not ok:
        raise HTTPException(404, f"Proposal not found: {proposal_key}")
    return {"rejected": True}


@router.post("/evolution/promote")
async def promote_proposals(threshold: float = 0.75) -> dict[str, int]:
    """Trigger auto-promote sweep (admin). Normally runs automatically every N sessions."""
    from backend.app.services.kg_evolution_service import get_kg_evolution

    return get_kg_evolution().promote_ready(threshold=threshold)


# ─────────────────────────────────────────────────────────────────────
# Multi-step verifier trace
# ─────────────────────────────────────────────────────────────────────


class VerifierCheckRequest(BaseModel):
    session_id: str
    expected: str
    actual: str
    domain: str = "math"  # math | chemistry | general


@router.post("/verifier/check")
async def run_verifier_check(req: VerifierCheckRequest) -> dict[str, Any]:
    """Run multi-step verification (SymPy + optional ChemPy) and store trace."""
    from src.agents.multistep_verifier import get_verifier_tracer

    tracer = get_verifier_tracer()
    result = tracer.verify(
        session_id=req.session_id,
        expected_answer=req.expected,
        student_response=req.actual,
        domain=req.domain,
    )
    return tracer.to_dict(result)


@router.get("/verifier/trace/{session_id}")
async def get_verifier_trace(session_id: str) -> dict[str, Any]:
    """Last verification trace for a session — for side-panel UI."""
    from src.agents.multistep_verifier import get_verifier_tracer

    tracer = get_verifier_tracer()
    result = tracer.get_trace(session_id)
    if result is None:
        raise HTTPException(404, f"No verifier trace for session {session_id}")
    return tracer.to_dict(result)


def _to_info(row: SourceTable) -> SourceInfo:
    preview = (row.content or "")[:160] + ("…" if len(row.content or "") > 160 else "")
    return SourceInfo(
        id=row.id,
        title=row.title,
        kind=row.kind,
        domain=row.domain,
        status=row.status,
        error=row.error,
        nodes_extracted=row.nodes_extracted,
        edges_extracted=row.edges_extracted,
        created_at=row.created_at,
        extracted_at=row.extracted_at,
        preview=preview,
    )
