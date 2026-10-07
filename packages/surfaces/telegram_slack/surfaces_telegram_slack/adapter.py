"""Telegram and Slack chat adapter stubs.

Owner: A1
"""

from typing import Any, Dict, Protocol

from contracts.models import Response


class ChatSurfaceAdapter(Protocol):
    """Protocol for surface adapters converting external chat payloads to pipeline events."""

    def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw platform payload into standard surface input dict."""
        ...

    def format_outbound(self, response: Response) -> Dict[str, Any]:
        """Convert standard pipeline Response into surface-specific payload."""
        ...


class TelegramAdapter:
    """Working stub adapter for Telegram bot webhook payloads."""

    def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # TODO (A1 Surface Owner): Handle inline keyboards, voice notes,
        # edit events, and telegram photo attachments.
        msg = payload.get("message", payload)
        user_info = msg.get("from", {})
        return {
            "surface_type": "telegram",
            "external_user_id": str(user_info.get("id", "telegram-user")),
            "text": msg.get("text", ""),
            "client_id": "telegram-bot-gateway",
            "channel_id": str(msg.get("chat", {}).get("id", "chat-001")),
            "is_interactive": True,
            "supports_markdown": False,
        }

    def format_outbound(self, response: Response) -> Dict[str, Any]:
        # Plain text without markdown formatting
        text = f"{response.routing_explanation}\n\n{response.reply_text}"
        return {
            "method": "sendMessage",
            "text": text,
            "parse_mode": None,
        }


class SlackAdapter:
    """Working stub adapter for Slack Events API payloads."""

    def parse_inbound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # TODO (A1 Surface Owner): Handle Block Kit interactions, slash commands,
        # thread replies, and workspace team IDs.
        event = payload.get("event", payload)
        return {
            "surface_type": "slack",
            "external_user_id": str(event.get("user", "slack-user")),
            "text": event.get("text", ""),
            "client_id": "slack-bot-gateway",
            "channel_id": str(event.get("channel", "C001")),
            "is_interactive": True,
            "supports_markdown": True,
        }

    def format_outbound(self, response: Response) -> Dict[str, Any]:
        return {
            "text": response.reply_text,
            "blocks": [
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"*{response.routing_explanation}*"}],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": response.reply_text},
                },
            ],
        }
