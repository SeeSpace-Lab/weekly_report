from .arxiv import ArxivCollector
from .crossref import CrossrefCollector
from .ieee_xplore import IeeeXploreCollector
from .openalex import OpenAlexCollector
from .github import GitHubCollector
from .huggingface import HuggingFaceCollector
from .manual import ManualInboxCollector
from .openreview import OpenReviewCollector
from .wechat import WechatPoolCollector
from .venue import VenueCollector

__all__ = [
    "ArxivCollector",
    "CrossrefCollector",
    "GitHubCollector",
    "HuggingFaceCollector",
    "ManualInboxCollector",
    "OpenReviewCollector",
    "WechatPoolCollector",
    "VenueCollector",
]
