import httpx
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from scripts.scraper.sources.base import BaseSource

logger = logging.getLogger(__name__)

class SCPWikiSource(BaseSource):
    @property
    def source_type(self) -> str:
        return "scp_wiki"
        
    async def fetch(self, niche_name: str, niche_config: Dict[str, Any], count: int) -> List[Dict[str, str]]:
        import random
        
        results = []
        fetched = 0
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for _ in range(50):
                    scp_num = random.randint(2, 7999)
                    scp_id = f"scp-{scp_num:03d}"
                    url = f"https://scp-wiki.wikidot.com/{scp_id}"
                    
                    response = await client.get(url, follow_redirects=True)
                    if response.status_code != 200:
                        continue
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_content = soup.find(id="page-content")
                    if not page_content:
                        continue
                        
                    title_elem = soup.find(id="page-title")
                    title = title_elem.text.strip() if title_elem else "Unknown SCP"
                    
                    paragraphs = page_content.find_all('p')
                    text_blocks = [p.text.strip() for p in paragraphs if len(p.text.strip()) > 20]
                    text = "\n\n".join(text_blocks)
                    
                    if len(text.split()) < 100:
                        continue
                        
                    source_url = str(response.url)
                    
                    # Add CC-BY-SA attribution automatically
                    text = f"ATTRIBUTION: This story is based on '{title}' from the SCP Foundation Wiki ({source_url}), released under CC-BY-SA 3.0.\n\n{text}"
                    
                    results.append({
                        "title": title,
                        "text": text,
                        "source_id": f"scp_{source_url.split('/')[-1]}"
                    })
                    fetched += 1
                    
                    if fetched >= count:
                        break
        except Exception as e:
            logger.error(f"Failed to fetch from SCP Wiki: {e}")
            
        return results
