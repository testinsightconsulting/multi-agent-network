"""API helper utilities for Gemini interaction."""
import time
import re
from typing import List, Optional, Any, Callable
from google.genai import types
from google.genai import errors as genai_errors
from src.utils.debug_helper import debug

def parse_retry_delay(error_msg: str) -> Optional[float]:
    """Extract retry delay in seconds from error message if present."""
    # Look for 'retryDelay': '56s' or similar
    match = re.search(r"'retryDelay':\s*'(\d+)s'", error_msg)
    if match:
        return float(match.group(1))
    
    # Also check for 'retryDelay': '3s'
    match = re.search(r"retryDelay:\s*(\d+)s", error_msg)
    if match:
        return float(match.group(1))
    
    return None

def generate_content_with_adaptive_retry(
    client: Any,
    model: str,
    history: List[types.Content],
    system_instruction: str,
    tools: List[Callable],
    max_retries: int = 5,
    base_delay: float = 2.0,
    agent_id: str = "agent"
) -> Optional[types.GenerateContentResponse]:
    """
    Generate content with adaptive retry logic.
    Prioritizes server-provided retryDelay, otherwise uses exponential backoff.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                ),
            )
        except genai_errors.ClientError as e:
            error_msg = str(e)
            debug(f"Gemini API Error ({agent_id}): {e}", status_code=getattr(e, "status_code", None))
            
            # If it's not a rate limit, raise immediately
            if "RESOURCE_EXHAUSTED" not in error_msg and getattr(e, "status_code", None) != 429:
                raise e
            
            if attempt == max_retries:
                print(f"\n[CRITICAL] API Rate Limit Exceeded for {agent_id}. Retries exhausted.")
                print(f"Error: {error_msg}\n")
                break

            # Try to get delay from error message
            delay = parse_retry_delay(error_msg)
            
            if delay:
                # Add a small buffer to the server-suggested delay
                delay += 1.0
                debug(f"Rate limit hit; server requested {delay}s wait", agent=agent_id, attempt=attempt + 1)
            else:
                # Exponential backoff: base * 2^attempt
                delay = base_delay * (2 ** attempt)
                debug(f"Rate limit hit; exponential backoff wait {delay}s", agent=agent_id, attempt=attempt + 1)
            
            print(f"[!] API Rate limit for {agent_id}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
            continue
            
    return None
