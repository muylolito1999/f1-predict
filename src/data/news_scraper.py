"""Web scraper for F1 upgrade news and rumors."""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# F1 team names for search queries
F1_TEAMS = [
    "Red Bull", "Ferrari", "McLaren", "Mercedes",
    "Aston Martin", "Alpine", "Williams", "RB",
    "Haas", "Sauber",
]


class NewsScraper:
    """Scrapes F1 upgrade/development news from multiple sources."""

    def __init__(self, sources: list[dict] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.sources = sources or self._default_sources()

    def _default_sources(self) -> list[dict]:
        return [
            {
                "name": "The Race",
                "search_url": "https://www.the-race.com/?s={query}",
            },
            {
                "name": "Planet F1",
                "search_url": "https://www.planetf1.com/?s={query}",
            },
            {
                "name": "Autosport",
                "search_url": "https://www.autosport.com/search/?query={query}",
            },
        ]

    def search_team_upgrades(self, team: str,
                              max_articles: int = 5) -> list[dict]:
        """Search for recent upgrade news for a specific team."""
        articles = []
        queries = [
            f"{team} F1 upgrade 2026",
            f"{team} F1 development update",
            f"{team} F1 technical",
        ]

        for source in self.sources:
            for query in queries:
                try:
                    found = self._search_source(source, query, max_articles)
                    articles.extend(found)
                except Exception as e:
                    logger.debug(f"Error searching {source['name']}: {e}")
                    continue

                if len(articles) >= max_articles:
                    break

        # Deduplicate by URL
        seen_urls = set()
        unique = []
        for article in articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                unique.append(article)

        return unique[:max_articles]

    def _search_source(self, source: dict, query: str,
                        max_results: int) -> list[dict]:
        """Search a single news source."""
        url = source["search_url"].format(query=quote_plus(query))
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.debug(f"Request failed for {url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []

        # Generic article link extraction
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filter for relevant articles
            if not text or len(text) < 20:
                continue

            keywords = ["upgrade", "development", "technical", "update",
                        "aero", "floor", "wing", "performance", "package"]
            if not any(kw in text.lower() for kw in keywords):
                continue

            # Normalize URL
            if href.startswith("/"):
                base = source.get("base_url", "")
                if not base:
                    parts = source["search_url"].split("/")
                    base = f"{parts[0]}//{parts[2]}"
                href = base + href

            if not href.startswith("http"):
                continue

            articles.append({
                "title": text,
                "url": href,
                "source": source["name"],
            })

            if len(articles) >= max_results:
                break

        return articles

    def fetch_article_text(self, url: str) -> str:
        """Extract article text content from a URL."""
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            # Try common article selectors
            article = (
                soup.find("article") or
                soup.find("div", class_="article-body") or
                soup.find("div", class_="post-content") or
                soup.find("main")
            )

            if article:
                return article.get_text(separator="\n", strip=True)
            return soup.get_text(separator="\n", strip=True)[:5000]
        except Exception as e:
            logger.warning(f"Failed to fetch article {url}: {e}")
            return ""

    def collect_all_teams(self, max_articles_per_team: int = 3) -> dict[str, list[dict]]:
        """Collect upgrade news for all F1 teams."""
        all_news = {}
        for team in F1_TEAMS:
            logger.info(f"Searching upgrade news for {team}...")
            articles = self.search_team_upgrades(team, max_articles_per_team)

            # Fetch full text for each article
            for article in articles:
                article["text"] = self.fetch_article_text(article["url"])

            all_news[team] = articles
            logger.info(f"  Found {len(articles)} articles for {team}")

        return all_news
