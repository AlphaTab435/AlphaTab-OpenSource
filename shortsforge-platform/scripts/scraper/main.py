import os
import sys
import random
import asyncio
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from scripts.scraper.core.database import init_db, check_exists, add_to_history
from scripts.scraper.core.config_loader import Config
from scripts.scraper.core.utils import create_staging_folder
from scripts.scraper.core.filter import evaluate_content, save_rejected_content
from scripts.scraper.core.polisher import polish_content

from scripts.scraper.sources.base import BaseSource
from scripts.scraper.sources.reddit import RedditSource
from scripts.scraper.sources.ai_generator import AIGeneratorSource
from scripts.scraper.sources.public_domain import PublicDomainSource
from scripts.scraper.sources.scp_wiki import SCPWikiSource
from scripts.scraper.sources.trends import TrendsSource

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Registry of available sources
SOURCES: Dict[str, BaseSource] = {
    "ai": AIGeneratorSource(),
    "public_domain": PublicDomainSource(),
    "scp_wiki": SCPWikiSource(),
    "trends": TrendsSource()
}

async def process_story(story: Dict[str, str], channel_name: str, niche_name: str, source_type: str) -> bool:
    """Processes a single scraped story. Returns True if saved successfully."""
    source_id = story["source_id"]
    title = story["title"]
    text = story["text"]
    
    if check_exists(source_id):
        logger.info(f"Skipping duplicate: {title} ({source_id})")
        return False
        
    logger.info(f"Evaluating: {title}")
    is_approved, reason = await evaluate_content(title, text)
    
    if not is_approved:
        logger.warning(f"Rejected: {title} | Reason: {reason}")
        save_rejected_content(title, reason, text)
        # Even if rejected, we add it to history so we don't scrape it and evaluate it again
        add_to_history(source_type, source_id, title, niche_name, channel_name)
        return False
        
    logger.info(f"Approved: {title}")
    
    # Pre-Polisher for massive/dry texts
    if source_type in ["scp_wiki", "public_domain"]:
        success, new_title, polished_text = await polish_content(title, text, source_type)
        if not success:
            logger.error(f"Discarding {title}: Failed to polish due to AI limits.")
            # We don't save to history if it failed polish, maybe we want to retry it later, 
            # but usually it's fine to just skip it this run.
            return False
            
        title = new_title
        text = polished_text
    
    # Save to staging
    folder_path = create_staging_folder(channel_name, title)
    file_path = os.path.join(folder_path, "1.txt")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
        
    add_to_history(source_type, source_id, title, niche_name, channel_name)
    return True


async def main():
    logger.info("Starting Automated Scraper")
    init_db()
    
    accounts = Config.get_accounts()
    niches_dict = Config.get_niches()
    
    all_niche_names = list(niches_dict.keys())
    all_source_names = list(SOURCES.keys())
    
    total_saved = 0
    
    for channel_name, acc_config in accounts.items():
        limit = acc_config.get("limit_per_run", 1)
        niches = acc_config.get("niches", [])
        source_names = acc_config.get("sources", [])
        
        # If empty, pick randomly
        if not niches:
            niches = [random.choice(all_niche_names)]
        if not source_names:
            source_names = [random.choice(all_source_names)]
            
        logger.info(f"Processing Account: {channel_name} | Target: {limit} stories")
        
        saved_for_channel = 0
        attempts = 0
        available_sources = source_names.copy()
        
        # Keep trying combinations until limit is reached or we exhaust reasonable attempts
        while saved_for_channel < limit and attempts < limit * 5 and available_sources:
            attempts += 1
            niche_name = random.choice(niches)
            source_name = random.choice(available_sources)
            
            niche_config = niches_dict.get(niche_name, {}).copy()
            niche_config["_is_shorts_only"] = acc_config.get("is_shorts_only", False)
            source_inst = SOURCES.get(source_name)
            
            if not source_inst:
                logger.error(f"Unknown source: {source_name}")
                available_sources.remove(source_name)
                continue
                
            # Fetch 1 story at a time so every single story can be a random niche/source combo!
            stories = await source_inst.fetch(niche_name, niche_config, count=1)
            
            if not stories:
                logger.error(f"Source '{source_name}' returned 0 stories. Removing from available sources for this channel.")
                available_sources.remove(source_name)
                continue
            
            for story in stories:
                if saved_for_channel >= limit:
                    break
                    
                success = await process_story(story, channel_name, niche_name, source_name)
                if success:
                    saved_for_channel += 1
                    total_saved += 1
                    
        if not available_sources and saved_for_channel < limit:
            logger.error(f"All sources failed for {channel_name}. Moving to next channel.")
                    
        logger.info(f"Finished {channel_name}: Saved {saved_for_channel}/{limit} stories.")

    if total_saved > 0:
        logger.info(f"Scraper completed successfully. Total stories saved: {total_saved}")
    else:
        logger.info("No new stories were saved. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())
