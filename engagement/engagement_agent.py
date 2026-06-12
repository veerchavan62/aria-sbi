"""
ARIA — Engagement Agent
Routes and dispatches personalized outreach via WhatsApp Business API,
YONO deep-links, Business Correspondent routing, and RM escalation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class OutreachChannel(str, Enum):
    WHATSAPP = "whatsapp"
    YONO = "yono"
    BC = "bc"
    RM = "rm"
    SMS = "sms"


@dataclass
class DispatchResult:
    prospect_id: str
    channel: OutreachChannel
    status: str          # "sent" | "failed" | "queued"
    message_id: str
    dispatched_at: str


class EngagementAgent:
    """
    Engagement Agent: selects optimal channel and dispatches outreach.

    Production integrations:
    - WhatsApp Business API (Meta)
    - YONO Deep Link SDK (SBI)
    - BC Agent Mobile App (SBI's internal system)
    - RM CRM system (Salesforce / SBI CRM)
    """

    def __init__(self):
        # In production: load API keys from env / secrets manager
        self._whatsapp_api_url = "https://graph.facebook.com/v18.0/messages"
        self._yono_deeplink_base = "sbi://yono/offer"
        logger.info("EngagementAgent initialized")

    def _dispatch_whatsapp(self, message_data: dict) -> DispatchResult:
        """Send WhatsApp Business API message (mock for demo)."""
        msg_id = f"wa_{message_data['prospect_id']}_{datetime.utcnow().strftime('%H%M%S')}"
        logger.info(f"[WhatsApp] Dispatched to {message_data['prospect_id']}: {message_data['whatsapp_message'][:60]}...")
        return DispatchResult(
            prospect_id=message_data["prospect_id"],
            channel=OutreachChannel.WHATSAPP,
            status="sent",
            message_id=msg_id,
            dispatched_at=datetime.utcnow().isoformat(),
        )

    def _dispatch_yono(self, message_data: dict) -> DispatchResult:
        """Trigger YONO app push notification with deep link (mock for demo)."""
        deep_link = f"{self._yono_deeplink_base}?product={message_data['product_id']}&pid={message_data['prospect_id']}"
        msg_id = f"yono_{message_data['prospect_id']}_{datetime.utcnow().strftime('%H%M%S')}"
        logger.info(f"[YONO] Push + deeplink for {message_data['prospect_id']}: {deep_link}")
        return DispatchResult(
            prospect_id=message_data["prospect_id"],
            channel=OutreachChannel.YONO,
            status="sent",
            message_id=msg_id,
            dispatched_at=datetime.utcnow().isoformat(),
        )

    def _dispatch_bc(self, message_data: dict) -> DispatchResult:
        """Route to nearest Business Correspondent with talking points (mock)."""
        msg_id = f"bc_{message_data['prospect_id']}_{datetime.utcnow().strftime('%H%M%S')}"
        logger.info(f"[BC] Assigned to BC agent for {message_data['prospect_id']}: {message_data['bc_script'][:60]}...")
        return DispatchResult(
            prospect_id=message_data["prospect_id"],
            channel=OutreachChannel.BC,
            status="queued",   # BC visits are scheduled, not instant
            message_id=msg_id,
            dispatched_at=datetime.utcnow().isoformat(),
        )

    def _dispatch_rm(self, message_data: dict) -> DispatchResult:
        """Escalate high-value prospect to Relationship Manager (mock)."""
        msg_id = f"rm_{message_data['prospect_id']}_{datetime.utcnow().strftime('%H%M%S')}"
        logger.info(f"[RM] Lead escalated to RM for {message_data['prospect_id']}")
        return DispatchResult(
            prospect_id=message_data["prospect_id"],
            channel=OutreachChannel.RM,
            status="sent",
            message_id=msg_id,
            dispatched_at=datetime.utcnow().isoformat(),
        )

    def dispatch(self, message_data: dict, channel: str) -> DispatchResult:
        """Dispatch a single personalized message via the specified channel."""
        dispatch_map = {
            "whatsapp": self._dispatch_whatsapp,
            "yono": self._dispatch_yono,
            "bc": self._dispatch_bc,
            "rm": self._dispatch_rm,
        }
        handler = dispatch_map.get(channel, self._dispatch_whatsapp)
        try:
            return handler(message_data)
        except Exception as e:
            logger.error(f"Dispatch failed for {message_data.get('prospect_id')}: {e}")
            return DispatchResult(
                prospect_id=message_data.get("prospect_id", "unknown"),
                channel=OutreachChannel(channel),
                status="failed",
                message_id="",
                dispatched_at=datetime.utcnow().isoformat(),
            )

    def dispatch_batch(
        self, messages: list[dict], channel_map: dict[str, str]
    ) -> tuple[list[dict], list[dict]]:
        """
        Dispatch all cleared messages.
        Returns (dispatched_results, failed_results).
        """
        dispatched = []
        failed = []
        for msg in messages:
            channel = channel_map.get(msg["prospect_id"], "whatsapp")
            result = self.dispatch(msg, channel)
            if result.status in ("sent", "queued"):
                dispatched.append(vars(result))
            else:
                failed.append(vars(result))
        return dispatched, failed
