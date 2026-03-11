"""Azure OpenAI integration for analyzing F1 upgrade news and rumors."""

import json
import logging
import os

from openai import AzureOpenAI

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are an F1 technical analyst. Analyze the following article about an F1 team's car development/upgrade and extract structured information.

Team: {team}
Article Title: {title}
Article Source: {source}

Article Text:
{text}

Extract the following information as JSON:
{{
    "has_upgrade": true/false,  // Does the article mention a specific car upgrade?
    "component": "string",     // One of: "front_wing", "rear_wing", "floor", "sidepods", "diffuser", "suspension", "power_unit", "cooling", "bodywork", "other", "none"
    "impact_score": float,     // Estimated performance impact from -1.0 (regression) to +1.0 (major gain). 0.0 if no clear upgrade.
    "confidence": "string",    // One of: "rumor", "confirmed", "tested"
    "sentiment": float,        // Overall sentiment about team's direction: -1.0 (very negative) to +1.0 (very positive)
    "summary": "string"        // One sentence summary of the upgrade or development news
}}

Be realistic with impact_score:
- 0.01 to 0.05: Minor upgrade (small aero tweak)
- 0.05 to 0.15: Moderate upgrade (new floor edge, wing endplate)
- 0.15 to 0.30: Major upgrade (significant aero package)
- 0.30 to 0.50: Game-changing upgrade (rare, like new concept direction)
- Negative values for known regressions or setbacks

Respond ONLY with valid JSON, no other text."""


class UpgradeAnalyzer:
    """Analyzes F1 upgrade articles using Azure OpenAI."""

    def __init__(self, endpoint: str = None, api_key: str = None,
                 deployment: str = "gpt-5-chat",
                 api_version: str = "2024-02-15-preview"):
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.deployment = deployment
        self.api_version = api_version
        self._client = None

    @property
    def client(self) -> AzureOpenAI:
        if self._client is None:
            if not self.endpoint or not self.api_key:
                raise ValueError(
                    "Azure OpenAI endpoint and API key must be configured. "
                    "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY env vars."
                )
            self._client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
            )
        return self._client

    def analyze_article(self, team: str, title: str, text: str,
                        source: str = "") -> dict:
        """Analyze a single article and return structured upgrade data."""
        if not text or len(text) < 50:
            return self._empty_result()

        # Truncate very long articles
        if len(text) > 4000:
            text = text[:4000] + "..."

        prompt = ANALYSIS_PROMPT.format(
            team=team, title=title, source=source, text=text
        )

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an F1 technical analyst. Respond only in valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON, handle markdown code blocks
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(content)
            return self._validate_result(result)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._empty_result()
        except Exception as e:
            logger.warning(f"Azure OpenAI API error: {e}")
            return self._empty_result()

    def analyze_team_articles(self, team: str,
                               articles: list[dict]) -> list[dict]:
        """Analyze multiple articles for a team."""
        results = []
        for article in articles:
            text = article.get("text", "")
            if not text:
                continue

            result = self.analyze_article(
                team=team,
                title=article.get("title", ""),
                text=text,
                source=article.get("source", ""),
            )
            result["url"] = article.get("url", "")
            result["source_name"] = article.get("source", "")
            results.append(result)

        return results

    def get_team_upgrade_summary(self, team: str,
                                  articles: list[dict]) -> dict:
        """Get aggregated upgrade summary for a team."""
        analyses = self.analyze_team_articles(team, articles)

        if not analyses:
            return {
                "upgrade_impact_score": 0.0,
                "upgrade_component": "none",
                "upgrade_sentiment": 0.0,
                "upgrade_confidence": "none",
                "article_count": 0,
            }

        # Aggregate scores
        impact_scores = [a["impact_score"] for a in analyses if a.get("has_upgrade")]
        sentiments = [a["sentiment"] for a in analyses]

        # Find the most significant upgrade
        upgrades = [a for a in analyses if a.get("has_upgrade")]
        top_component = "none"
        top_confidence = "none"
        if upgrades:
            top = max(upgrades, key=lambda x: abs(x.get("impact_score", 0)))
            top_component = top.get("component", "none")
            top_confidence = top.get("confidence", "rumor")

        return {
            "upgrade_impact_score": sum(impact_scores) / len(impact_scores) if impact_scores else 0.0,
            "upgrade_component": top_component,
            "upgrade_sentiment": sum(sentiments) / len(sentiments) if sentiments else 0.0,
            "upgrade_confidence": top_confidence,
            "article_count": len(analyses),
            "details": analyses,
        }

    def _validate_result(self, result: dict) -> dict:
        """Ensure result has all required fields with valid values."""
        validated = {
            "has_upgrade": bool(result.get("has_upgrade", False)),
            "component": str(result.get("component", "none")),
            "impact_score": max(-1.0, min(1.0, float(result.get("impact_score", 0.0)))),
            "confidence": str(result.get("confidence", "rumor")),
            "sentiment": max(-1.0, min(1.0, float(result.get("sentiment", 0.0)))),
            "summary": str(result.get("summary", "")),
        }
        return validated

    def _empty_result(self) -> dict:
        return {
            "has_upgrade": False,
            "component": "none",
            "impact_score": 0.0,
            "confidence": "none",
            "sentiment": 0.0,
            "summary": "",
        }
