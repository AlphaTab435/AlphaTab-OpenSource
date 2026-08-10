import re

def extract_trailers(full_text: str, count: int) -> list:
    """Return `count` non-overlapping teaser snippets from `full_text`.
    * It explicitly extracts the hook (first sentence) and prepends it to EVERY trailer.
    * It slices strictly on sentence boundaries (., ?, !) to prevent mid-sentence cropping.
    """
    if not full_text.strip():
        return []
        
    # 1. Extract the hook (first sentence)
    match = re.search(r'[.?!]', full_text)
    if match:
        hook_end = match.end()
        hook = full_text[:hook_end].strip()
        remaining_text = full_text[hook_end:].strip()
    else:
        # Fallback if no punctuation
        words = full_text.split()
        hook = " ".join(words[:25])
        remaining_text = " ".join(words[25:])
        
    # Split text into sentences safely
    def get_sentences(text):
        return [s.strip() for s in re.split(r'(?<=[.?!])\s+', text) if s.strip()]
        
    if count <= 1:
        # For 1 trailer, we just return the first ~130 words starting with the hook
        sentences = get_sentences(full_text)
        trailer = []
        word_cnt = 0
        for s in sentences:
            trailer.append(s)
            word_cnt += len(s.split())
            if word_cnt >= 130:
                break
        return [" ".join(trailer)]

    # We need to extract multiple snippets from remaining_text
    sentences = get_sentences(remaining_text)
    total_sentences = len(sentences)
    
    if total_sentences == 0:
        return [hook] * count
        
    def get_snippet(start_idx, target_words=120):
        snippet = []
        word_cnt = 0
        idx = start_idx
        while idx < total_sentences and word_cnt < target_words:
            s = sentences[idx]
            snippet.append(s)
            word_cnt += len(s.split())
            idx += 1
        return " ".join(snippet)
        
    snippets = []
    
    # Trailer 1: Hook + immediately following sentences
    snippets.append(hook + " " + get_snippet(0))
    
    if count > 1:
        # Trailer 2: Hook + middle chunk
        middle_idx = max(1, total_sentences // 3)
        snippets.append(hook + " " + get_snippet(middle_idx))
        
    if count > 2:
        # Trailer 3: Hook + second-last quarter chunk
        second_last_idx = max(1, int(total_sentences * 0.6))
        snippets.append(hook + " " + get_snippet(second_last_idx))
        
    return snippets[:count]
