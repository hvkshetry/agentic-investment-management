"""Text chunking utilities for managing token limits."""

from typing import List, Dict, Any


def estimate_tokens(text: str) -> int:
    """Estimate token count using simple heuristic.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    # Rough approximation: 4 characters per token
    return len(text) // 4


def chunk_text_by_tokens(text: str, max_tokens: int = 4500) -> List[Dict[str, Any]]:
    """Split text into chunks under token limit.

    Attempts to split on paragraph boundaries when possible.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk

    Returns:
        List of chunk dicts with 'text', 'index', and 'tokens' fields
    """
    if estimate_tokens(text) <= max_tokens:
        return [{
            "text": text,
            "index": 0,
            "tokens": estimate_tokens(text),
            "is_continuation": False
        }]

    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = []
    current_tokens = 0
    chunk_index = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # If single paragraph exceeds limit, split by sentences
        if para_tokens > max_tokens:
            # Flush current chunk first
            if current_chunk:
                chunks.append({
                    "text": '\n\n'.join(current_chunk),
                    "index": chunk_index,
                    "tokens": current_tokens,
                    "is_continuation": chunk_index > 0
                })
                chunk_index += 1
                current_chunk = []
                current_tokens = 0

            # Split oversized paragraph by sentences
            sentences = para.split('. ')
            for i, sent in enumerate(sentences):
                sent_with_period = sent if sent.endswith('.') else sent + '.'
                sent_tokens = estimate_tokens(sent_with_period)

                if current_tokens + sent_tokens > max_tokens and current_chunk:
                    # Flush chunk
                    chunks.append({
                        "text": ' '.join(current_chunk),
                        "index": chunk_index,
                        "tokens": current_tokens,
                        "is_continuation": chunk_index > 0
                    })
                    chunk_index += 1
                    current_chunk = [sent_with_period]
                    current_tokens = sent_tokens
                else:
                    current_chunk.append(sent_with_period)
                    current_tokens += sent_tokens

        # Normal case: add paragraph to current chunk
        elif current_tokens + para_tokens <= max_tokens:
            current_chunk.append(para)
            current_tokens += para_tokens
        else:
            # Flush current chunk and start new one
            chunks.append({
                "text": '\n\n'.join(current_chunk),
                "index": chunk_index,
                "tokens": current_tokens,
                "is_continuation": chunk_index > 0
            })
            chunk_index += 1
            current_chunk = [para]
            current_tokens = para_tokens

    # Add final chunk
    if current_chunk:
        chunks.append({
            "text": '\n\n'.join(current_chunk) if isinstance(current_chunk[0], str) and '\n' not in current_chunk[0][:50] else ' '.join(current_chunk),
            "index": chunk_index,
            "tokens": current_tokens,
            "is_continuation": chunk_index > 0
        })

    return chunks
