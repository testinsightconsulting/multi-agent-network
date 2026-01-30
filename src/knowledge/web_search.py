"""Web search for documentation"""
from typing import Optional
import os


class WebSearch:
    """Web search for documentation (using Gemini's web search or external API)"""
    
    def __init__(self, use_gemini_web_search: bool = True):
        self.use_gemini_web_search = use_gemini_web_search
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    def search(self, query: str, max_results: int = 3) -> str:
        """Search the web for documentation"""
        if self.use_gemini_web_search:
            # Gemini API has built-in web search in some models
            # Return instruction for agent to use Gemini's capability
            return f"Use Gemini's web search capability to find: {query}"
        
        # Alternative: Use external search API (Serper, Tavily, etc.)
        if self.serper_api_key:
            return self._search_serper(query, max_results)
        elif self.tavily_api_key:
            return self._search_tavily(query, max_results)
        
        return f"Web search for: {query} (no API key configured)"
    
    def _search_serper(self, query: str, max_results: int) -> str:
        """Search using Serper API"""
        try:
            import httpx
            response = httpx.post(
                "https://google.serper.dev/search",
                json={"q": query},
                headers={"X-API-KEY": self.serper_api_key},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("organic", [])[:max_results]:
                    results.append(f"{item.get('title', '')}: {item.get('snippet', '')}")
                return "\n".join(results)
        except Exception as e:
            return f"Error searching: {e}"
        return ""
    
    def _search_tavily(self, query: str, max_results: int) -> str:
        """Search using Tavily API"""
        try:
            import httpx
            response = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": self.tavily_api_key, "query": query, "max_results": max_results},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("results", []):
                    results.append(f"{item.get('title', '')}: {item.get('content', '')[:200]}")
                return "\n".join(results)
        except Exception as e:
            return f"Error searching: {e}"
        return ""

