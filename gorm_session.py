"""
Gorm Session
=============
Per-Gorm session model. Each Gorm has its own watcher session
with domain-specific sources, seen hashes, and signal state.
"""

import hashlib
from dataclasses import dataclass, field

# Sources per domain — real URLs that MFYP watches
GORM_SOURCES: dict[str, list[dict]] = {
    "market": [
        {"url": "https://www.reddit.com/r/flipping/.rss", "type": "rss", "label": "r/flipping"},
        {"url": "https://www.reddit.com/r/Flipping/.rss", "type": "rss", "label": "r/Flipping"},
        {"url": "https://www.reddit.com/r/thriftstorehauls/.rss", "type": "rss", "label": "r/thriftstorehauls"},
    ],
    "finance": [
        {"url": "https://www.reddit.com/r/investing/.rss", "type": "rss", "label": "r/investing"},
        {"url": "https://www.reddit.com/r/wallstreetbets/.rss", "type": "rss", "label": "r/wallstreetbets"},
        {"url": "https://news.ycombinator.com/rss", "type": "rss", "label": "Hacker News"},
    ],
    "tech & AI": [
        {"url": "https://news.ycombinator.com/rss", "type": "rss", "label": "Hacker News"},
        {"url": "https://www.reddit.com/r/MachineLearning/.rss", "type": "rss", "label": "r/MachineLearning"},
        {"url": "https://www.reddit.com/r/artificial/.rss", "type": "rss", "label": "r/artificial"},
    ],
    "law": [
        {"url": "https://www.reddit.com/r/legaladvice/.rss", "type": "rss", "label": "r/legaladvice"},
        {"url": "https://www.reddit.com/r/smallbusiness/.rss", "type": "rss", "label": "r/smallbusiness"},
    ],
    "cybersec": [
        {"url": "https://www.reddit.com/r/netsec/.rss", "type": "rss", "label": "r/netsec"},
        {"url": "https://news.ycombinator.com/rss", "type": "rss", "label": "Hacker News"},
    ],
    "science": [
        {"url": "https://www.reddit.com/r/science/.rss", "type": "rss", "label": "r/science"},
    ],
    "real estate": [
        {"url": "https://www.reddit.com/r/realestateinvesting/.rss", "type": "rss", "label": "r/realestateinvesting"},
    ],
    "supply chain": [
        {"url": "https://www.reddit.com/r/supplychain/.rss", "type": "rss", "label": "r/supplychain"},
    ],
    "career": [
        {"url": "https://www.reddit.com/r/careerguidance/.rss", "type": "rss", "label": "r/careerguidance"},
    ],
    "music": [
        {"url": "https://www.reddit.com/r/WeAreTheMusicMakers/.rss", "type": "rss", "label": "r/WeAreTheMusicMakers"},
    ],
}


@dataclass
class GormSession:
    """Represents one Gorm's active watching session."""
    gorm_id: int
    gorm_name: str
    user_id: str
    domain: str
    biome: str
    level: int = 1
    sources: list[dict] = field(default_factory=list)
    seen_hashes: set[str] = field(default_factory=set)
    signal_count: int = 0
    high_count: int = 0

    def __post_init__(self):
        if not self.sources:
            self.sources = get_sources_for_domain(self.domain)

    def has_seen(self, content: str) -> bool:
        h = hashlib.md5(content[:200].encode()).hexdigest()
        if h in self.seen_hashes:
            return True
        self.seen_hashes.add(h)
        return False

    def record_signal(self, strength: str):
        self.signal_count += 1
        if strength == "HIGH":
            self.high_count += 1


def get_sources_for_domain(domain: str) -> list[dict]:
    """Get watching sources for a domain. Falls back to HN if no specific sources."""
    domain_lower = domain.lower()
    for key, sources in GORM_SOURCES.items():
        if key in domain_lower or domain_lower in key:
            return sources
    # Fallback: Hacker News (general tech)
    return [{"url": "https://news.ycombinator.com/rss", "type": "rss", "label": "Hacker News"}]
