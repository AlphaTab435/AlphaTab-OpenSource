from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class BaseSource(ABC):
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Returns the unique identifier for this source (e.g., 'reddit', 'ai', 'scp_wiki')."""
        pass

    @abstractmethod
    async def fetch(self, niche_name: str, niche_config: Dict[str, Any], count: int) -> List[Dict[str, str]]:
        """
        Fetches `count` number of stories for the given niche.
        Must return a list of dictionaries, each containing:
        {
            "title": "Story Title",
            "text": "The full story text...",
            "source_id": "unique_id_123"  # To prevent duplicates
        }
        """
        pass
