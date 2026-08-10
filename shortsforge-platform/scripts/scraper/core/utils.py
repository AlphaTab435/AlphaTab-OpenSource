import re
import os
import shutil

def sanitize_topic_name(title: str, max_length: int = 50) -> str:
    """
    Sanitizes a string to be safe for OS folder names and truncates it.
    """
    # Remove all non-alphanumeric characters except spaces, dashes, and underscores
    sanitized = re.sub(r'[^\w\s-]', '', title)
    
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Truncate to max_length without cutting words in half if possible
    if len(sanitized) > max_length:
        truncated = sanitized[:max_length].rsplit(' ', 1)[0]
        # Fallback if there were no spaces
        sanitized = truncated if truncated else sanitized[:max_length]
        
    return sanitized

def create_staging_folder(channel_name: str, topic_name: str) -> str:
    """
    Creates the directory structure for staging files.
    Returns the absolute path to the directory.
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    target_dir = os.path.join(base_dir, "output", "staging", channel_name, sanitize_topic_name(topic_name))
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

