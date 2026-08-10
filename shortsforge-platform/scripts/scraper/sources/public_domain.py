import httpx
import logging
from typing import List, Dict, Any
from scripts.scraper.sources.base import BaseSource

logger = logging.getLogger(__name__)

class PublicDomainSource(BaseSource):
    @property
    def source_type(self) -> str:
        return "public_domain"
        
    async def fetch(self, niche_name: str, niche_config: Dict[str, Any], count: int) -> List[Dict[str, str]]:
        topic = niche_name.split()[0].lower()
        if "horror" in topic or "scary" in topic:
            topic = "horror"
        elif "drama" in topic or "relationship" in topic:
            topic = "drama"
            
        url = f"https://gutendex.com/books/?topic={topic}&languages=en"
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.error(f"Gutendex API returned {response.status_code}")
                    return []
                    
                data = response.json()
                books = data.get("results", [])
                
                fetched = 0
                for book in books:
                    formats = book.get("formats", {})
                    txt_url = formats.get("text/plain") or formats.get("text/plain; charset=utf-8") or formats.get("text/plain; charset=us-ascii")
                    if not txt_url:
                        continue
                        
                    txt_resp = await client.get(txt_url, follow_redirects=True)
                    if txt_resp.status_code == 200:
                        text = txt_resp.text
                        
                        start_idx = text.find("*** START OF")
                        if start_idx != -1:
                            # Skip ahead past the preamble
                            nl_idx = text.find("\n", start_idx)
                            if nl_idx != -1:
                                text = text[nl_idx:]
                                
                        # Clip massive books to a reasonable snippet (e.g. 2000 words)
                        words = text.split()[:2000]
                        clipped_text = " ".join(words)
                        
                        results.append({
                            "title": book.get("title", f"Public Domain {topic}"),
                            "text": clipped_text,
                            "source_id": f"gutenberg_{book['id']}"
                        })
                        fetched += 1
                        
                    if fetched >= count:
                        break
        except Exception as e:
            logger.error(f"Failed to fetch from Gutendex: {e}")
            
        return results
