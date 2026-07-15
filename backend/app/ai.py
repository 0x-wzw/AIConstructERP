"""AI agent for ConstructERP — OCR, natural language commands, daily briefing.

Supports OpenAI and Ollama as LLM backends. When no backend is configured
(ai_provider="disabled" or missing API key), endpoints degrade gracefully
with informative messages instead of crashing.

The agent is lazily initialized on first use and can re-initialize if the
underlying provider becomes available later (e.g. Ollama started after API).
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from .config import settings

logger = logging.getLogger("constructerp.ai")


class AIAgent:
    def __init__(self):
        self.provider = settings.ai_provider
        self.client = None
        self.model = "unknown"
        self._initialized = False

    def _init_client(self):
        """Initialize the LLM client. Called lazily on first use or re-init."""
        self.client = None
        self.model = "unknown"
        if self.provider == "openai" and settings.openai_api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.openai_api_key)
                self.model = "gpt-4o-mini"
            except ImportError:
                logger.warning("openai package not installed — AI disabled")
        elif self.provider == "ollama":
            try:
                from openai import OpenAI as OllamaClient
                self.client = OllamaClient(
                    base_url=settings.ollama_base_url,
                    api_key="ollama",
                )
                self.model = settings.ollama_model or "llama3.2"
            except ImportError:
                logger.warning("openai package not installed — AI disabled")
        self._initialized = True

    def is_available(self) -> bool:
        """Check if the AI agent is ready. Re-initializes if not yet done."""
        if not self._initialized:
            self._init_client()
        return self.client is not None

    def reinit(self):
        """Force re-initialization (e.g. after settings change)."""
        self._initialized = False
        self._init_client()

    def _call_llm(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if not self.is_available():
            return "AI agent not configured. Set AI_PROVIDER and corresponding API key."
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return f"AI error: {str(e)}"

    # ── Natural Language Commands ────────────────────────────────────

    def process_command(self, command: str, data_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a natural language command against the ERP data.

        NOTE: The returned action is advisory only — it describes what the
        AI thinks should be done but does NOT execute it. The frontend or
        caller must confirm and execute via the normal API endpoints.
        """
        system = """You are an AI assistant for ConstructERP, a construction project management system.
Interpret the user's natural language command and return a JSON response with:
- "action": the type of action (query, create, update, delete, summarize, error)
- "entity": the entity type (project, task, po, budget, sub, resource, file)
- "filters": any filters to apply (dict)
- "message": human-readable response
- "data": any data to create/update (if applicable)

IMPORTANT: You are advisory only. You describe what should be done but do not
execute it. The user must confirm and execute via the normal API.

Respond ONLY with valid JSON, no markdown."""

        result = self._call_llm(
            system,
            f"User command: {command}\n\nAvailable data context: {json.dumps(data_context, default=str)[:2000]}",
            max_tokens=800,
        )

        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"action": "error", "message": result}
        except json.JSONDecodeError:
            return {"action": "query", "message": result}

    # ── Daily Briefing ───────────────────────────────────────────────

    def generate_briefing(self, data: Dict[str, Any]) -> str:
        """Generate a morning briefing with project status, alerts, and suggestions."""
        system = """You are a project management assistant for a construction company.
Generate a concise morning briefing covering:
1. Project status summary
2. Upcoming deadlines (next 7 days)
3. Budget alerts (over 80% spent)
4. Overdue items
5. Suggested actions for today

Keep it under 300 words. Be specific with numbers."""

        return self._call_llm(
            system,
            f"Generate briefing from this data:\n{json.dumps(data, default=str)[:3000]}",
            max_tokens=600,
        )

    # ── Budget Analysis ─────────────────────────────────────────────

    def analyze_budget(self, budget_data: List[Dict]) -> str:
        """Analyze budget data for overruns, trends, and recommendations."""
        system = """You are a construction cost analyst. Analyze the budget data and provide:
1. Categories at risk of overrun (>80% spent)
2. Overall budget health
3. Cost-saving recommendations
Be concise and specific."""

        return self._call_llm(
            system,
            f"Budget data:\n{json.dumps(budget_data, default=str)}",
            max_tokens=500,
        )

    # ── Chat ─────────────────────────────────────────────────────────

    def chat(self, message: str, history: List[Dict], data_context: Dict[str, Any]) -> str:
        """Conversational AI assistant with context awareness."""
        system = f"""You are ConstructAI, the AI assistant for ConstructERP.
You help construction project managers with their daily work.
You can answer questions about projects, budgets, schedules, and procurement.
Current data summary: {json.dumps({k: len(v) if isinstance(v, list) else v for k, v in data_context.items()}, default=str)[:500]}

Be helpful, concise, and specific. If you need data the user hasn't provided, ask for it."""

        messages = [{"role": "system", "content": system}]
        for h in history[-10:]:
            messages.append(h)
        messages.append({"role": "user", "content": message})

        if not self.is_available():
            return "AI agent not configured. Set AI_PROVIDER and corresponding API key."

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=800,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Chat LLM call failed: %s", e)
            return f"AI error: {str(e)}"


# Singleton — lazily initialized on first use.
ai_agent = AIAgent()