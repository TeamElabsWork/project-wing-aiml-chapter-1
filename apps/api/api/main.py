"""FastAPI Ingress Service for Surface-Aware Agent Orchestration.

Exposes /healthz, /v1/message, /v1/stream (SSE), /v1/webhooks/*, and /v1/approvals/*.
"""

import json
from typing import Any, AsyncIterator, Dict, Optional

from contracts.models import ApprovalResponse, Response
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
    async def telegram_webhook(
        request: Request,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ) -> Any:
        """Ingress webhook for Telegram updates with idempotency deduplication."""
        data = await request.json()
        message = data.get("message", {})
        text = message.get("text", "")
        sender = str(message.get("from", {}).get("id", "telegram-user"))
        chat_id = str(message.get("chat", {}).get("id", "telegram-chat"))

        # Idempotency resolution: update_id -> message_id -> Idempotency-Key header
        idem_key: Optional[str] = None
        if data.get("update_id") is not None:
            idem_key = str(data["update_id"])
        elif message.get("message_id") is not None:
            idem_key = str(message["message_id"])
        elif idempotency_key:
            idem_key = str(idempotency_key)

        if idem_key:
            cached = await app_idempotency.get(idem_key)
            if cached:
                return JSONResponse(
                    content=cached,
                    headers={"X-Idempotent-Replay": "true"},
                )

        resp = await app_pipeline.process(
            raw_input=text,
            surface_type="telegram",
            external_user_id=sender,
            session_id=f"tg-{chat_id}",
            metadata={"telegram_chat_id": chat_id, "telegram_raw": data},
        )
        resp_dict = resp.model_dump(mode="json")
        if idem_key:
            await app_idempotency.set(idem_key, resp_dict)
        return resp_dict

    @app.post("/v1/webhooks/slack")
    async def slack_webhook(
        request: Request,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ) -> Any:
        """Ingress webhook for Slack Events API with idempotency deduplication."""
        data = await request.json()
        # Handle Slack URL verification challenge
        if data.get("type") == "url_verification":
            return {"challenge": data.get("challenge")}

        event = data.get("event", {})
        text = event.get("text", "")
        user = str(event.get("user", "slack-user"))
        channel = str(event.get("channel", "slack-channel"))

        # Idempotency resolution: event_id -> client_msg_id -> Idempotency-Key header
        idem_key: Optional[str] = None
        if data.get("event_id") is not None:
            idem_key = str(data["event_id"])
        elif event.get("client_msg_id") is not None:
            idem_key = str(event["client_msg_id"])
        elif idempotency_key:
            idem_key = str(idempotency_key)

        if idem_key:
            cached = await app_idempotency.get(idem_key)
            if cached:
                return JSONResponse(
                    content=cached,
                    headers={"X-Idempotent-Replay": "true"},
                )

        resp = await app_pipeline.process(
            raw_input=text,
            surface_type="slack",
            external_user_id=user,
            session_id=f"slack-{channel}",
            metadata={"slack_channel": channel, "slack_raw": data},
        )
        resp_dict = resp.model_dump(mode="json")
        if idem_key:
            await app_idempotency.set(idem_key, resp_dict)
        return resp_dict

    @app.get("/v1/approvals/{request_id}")
    async def get_approval(request_id: str) -> Any:
        """Retrieve a pending approval request."""
        req = await app_pipeline.approval_manager.get_pending(request_id)
        if not req:
            return JSONResponse(
                status_code=404, content={"error": f"Request '{request_id}' not found."}
            )
        return req.model_dump(mode="json")

    @app.post("/v1/approvals/{request_id}")
    async def submit_approval(
        request_id: str,
        decision: ApprovalDecisionRequest,
    ) -> Dict[str, Any]:
        """Record an approval decision for an action request and execute/resume if approved."""
        approval_response = ApprovalResponse(
            approved=decision.approved,
            feedback=decision.feedback,
            approver=decision.approver_id,
            pending=False,
        )
        res = await app_pipeline.approval_manager.submit_decision(
            request_id=request_id,
            decision=approval_response,
        )
        if not res:
            return {"error": f"Request '{request_id}' not found.", "status": "not_found"}
        record: Dict[str, Any] = {
            "request_id": request_id,
            "approved": res.approved,
            "approver_id": res.approver or decision.approver_id,
            "feedback": res.feedback,
            "status": "approved" if res.approved else "denied",
        }
        exec_results = getattr(app_pipeline.approval_manager, "execution_results", {})
        if request_id in exec_results:
            tr = exec_results[request_id]
            record["tool_result"] = tr.model_dump(mode="json")
        return record

    return app


app = create_app()
