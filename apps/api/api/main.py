"""FastAPI Ingress Service for Surface-Aware Agent Orchestration.

Exposes /healthz, /v1/message, /v1/stream (SSE), /v1/webhooks/*, and /v1/approvals/*.
"""

import json
from typing import Any, AsyncIterator, Dict, Optional

from contracts.models import Response
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from orchestrator.pipeline import OrchestratorPipeline, create_pipeline
from pydantic import BaseModel, Field

from api.idempotency import IdempotencyStore, InMemoryIdempotencyStore


class MessageRequest(BaseModel):
    """Input payload for user message processing."""

    text: str = Field(..., description="Message text from user.")
    surface_type: str = Field(
        default="api", description="Surface category (cli, slack, telegram, api)."
    )
    user_id: str = Field(default="api-user", description="External user identifier.")
    session_id: Optional[str] = Field(default=None, description="Optional conversation session ID.")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Arbitrary context metadata."
    )


class ApprovalDecisionRequest(BaseModel):
    """Payload for submitting a human or policy approval decision."""

    approved: bool = Field(..., description="Whether the requested action is approved.")
    approver_id: str = Field(default="human-operator", description="Identifier of the approver.")
    feedback: Optional[str] = Field(
        default=None, description="Optional feedback or rejection reason."
    )


def create_app(
    pipeline: Optional[OrchestratorPipeline] = None,
    idempotency_store: Optional[IdempotencyStore] = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Surface-Aware Agent Orchestration API",
        version="0.2.0",
        description="Ingress API gateway with SSE streaming and idempotency deduplication.",
    )

    app_pipeline = pipeline or create_pipeline()
    app_idempotency = idempotency_store or InMemoryIdempotencyStore()
    approvals_db: Dict[str, Dict[str, Any]] = {}

    @app.get("/healthz")
    async def healthz() -> Dict[str, str]:
        """Liveness and readiness health probe."""
        return {"status": "ok", "version": "0.2.0"}

    @app.post("/v1/message", response_model=Response)
    async def post_message(
        req: MessageRequest,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ) -> Any:
        """Process inbound message with optional Idempotency-Key deduplication."""
        if idempotency_key:
            cached = await app_idempotency.get(idempotency_key)
            if cached:
                return JSONResponse(
                    content=cached,
                    headers={"X-Idempotent-Replay": "true"},
                )

        resp = await app_pipeline.process(
            raw_input=req.text,
            surface_type=req.surface_type,
            external_user_id=req.user_id,
            session_id=req.session_id,
            metadata=req.metadata,
        )

        resp_dict = resp.model_dump(mode="json")
        if idempotency_key:
            await app_idempotency.set(idempotency_key, resp_dict)

        return resp

    @app.post("/v1/stream")
    async def post_stream(req: MessageRequest) -> StreamingResponse:
        """Stream response tokens or events via Server-Sent Events (SSE)."""

        async def event_generator() -> AsyncIterator[str]:
            async for chunk in app_pipeline.stream(
                raw_input=req.text,
                surface_type=req.surface_type,
                external_user_id=req.user_id,
                session_id=req.session_id,
                metadata=req.metadata,
            ):
                payload = json.dumps({"chunk": chunk})
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/v1/webhooks/telegram")
    async def telegram_webhook(request: Request) -> Dict[str, Any]:
        """Ingress webhook for Telegram updates."""
        data = await request.json()
        message = data.get("message", {})
        text = message.get("text", "")
        sender = str(message.get("from", {}).get("id", "telegram-user"))
        chat_id = str(message.get("chat", {}).get("id", "telegram-chat"))

        resp = await app_pipeline.process(
            raw_input=text,
            surface_type="telegram",
            external_user_id=sender,
            session_id=f"tg-{chat_id}",
            metadata={"telegram_chat_id": chat_id, "telegram_raw": data},
        )
        return resp.model_dump(mode="json")

    @app.post("/v1/webhooks/slack")
    async def slack_webhook(request: Request) -> Any:
        """Ingress webhook for Slack Events API."""
        data = await request.json()
        # Handle Slack URL verification challenge
        if data.get("type") == "url_verification":
            return {"challenge": data.get("challenge")}

        event = data.get("event", {})
        text = event.get("text", "")
        user = str(event.get("user", "slack-user"))
        channel = str(event.get("channel", "slack-channel"))

        resp = await app_pipeline.process(
            raw_input=text,
            surface_type="slack",
            external_user_id=user,
            session_id=f"slack-{channel}",
            metadata={"slack_channel": channel, "slack_raw": data},
        )
        return resp.model_dump(mode="json")

    @app.post("/v1/approvals/{request_id}")
    async def submit_approval(
        request_id: str,
        decision: ApprovalDecisionRequest,
    ) -> Dict[str, Any]:
        """Record an approval decision for an action request."""
        record = {
            "request_id": request_id,
            "approved": decision.approved,
            "approver_id": decision.approver_id,
            "feedback": decision.feedback,
            "status": "approved" if decision.approved else "denied",
        }
        approvals_db[request_id] = record
        return record

    return app


app = create_app()
