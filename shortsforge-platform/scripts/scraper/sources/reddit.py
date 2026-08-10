# [DROPPED] Due to Reddit's "Responsible Builder Policy" banning automated/commercial API usage.
import os
import praw
import logging
import asyncio
from typing import List, Dict, Any
from scripts.scraper.sources.base import BaseSource
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.config import get_env

logger = logging.getLogger(__name__)

class RedditSource(BaseSource):
    @property
    def source_type(self) -> str:
        return "reddit"
        
    async def fetch(self, niche_name: str, niche_config: Dict[str, Any], count: int) -> List[Dict[str, str]]:
        client_id = get_env("REDDIT_CLIENT_ID")
        client_secret = get_env("REDDIT_CLIENT_SECRET")
        user_agent = get_env("REDDIT_USER_AGENT") or "python:shortsforge.scraper:v1.0 (by /u/shortsforge)"
        
        if not (client_id and client_secret):
            logger.error("REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not found. Skipping Reddit.")
            return []
            
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        subreddits = niche_config.get("reddit", [])
        if not subreddits:
            logger.warning(f"No subreddits defined for niche: {niche_name}")
            return []
            
        multi_sub = "+".join(subreddits)
        
        results = []
        try:
            def fetch_posts():
                posts = []
                subreddit = reddit.subreddit(multi_sub)
                for submission in subreddit.hot(limit=count * 3):
                    if submission.is_self and submission.selftext:
                        if len(submission.selftext.split()) > 100:
                            posts.append(submission)
                            if len(posts) >= count:
                                break
                return posts
                
            submissions = await asyncio.to_thread(fetch_posts)
            
            for sub in submissions:
                results.append({
                    "title": sub.title,
                    "text": sub.selftext,
                    "source_id": f"t3_{sub.id}"
                })
        except Exception as e:
            logger.error(f"Failed to fetch from Reddit: {e}")
            
        return results

# [DROPPED] Due to Reddit's "Responsible Builder Policy" banning automated/commercial API usage.
