# search_provider.py
"""
JARVIS Search Provider

Web search capability using DuckDuckGo HTML scraping.
Simple, free, no API key required.

Features:
- DuckDuckGo HTML search
- Result caching to avoid duplicate queries
- Clean result formatting
- Easy to extend with other providers later
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import hashlib


class SearchResult:
    """Single search result"""
    
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet
        }
    
    def __str__(self) -> str:
        return f"{self.title}\n{self.url}\n{self.snippet}"


class SearchProvider:
    """
    Web search provider using DuckDuckGo HTML scraping.
    
    Features:
    - Free, no API key needed
    - Result caching (5 minute TTL)
    - Clean HTML parsing
    - Fallback handling
    """
    
    def __init__(self, jarvis_core=None):
        """
        Initialize search provider
        
        Args:
            jarvis_core: Optional reference to JarvisCore for logging
        """
        self.core = jarvis_core
        self.cache = {}  # query_hash -> (results, timestamp)
        self.cache_ttl = timedelta(minutes=5)
        
        # Statistics
        self.stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "failures": 0,
            "total_results": 0
        }
    
    def _log(self, category: str, message: str):
        """Log message (uses core if available, otherwise prints)"""
        if self.core:
            self.core._log(category, message)
        else:
            print(f"[{category}] {message}")
    
    def _get_cache_key(self, query: str, num_results: int) -> str:
        """Generate cache key for query"""
        key_str = f"{query.lower().strip()}:{num_results}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _check_cache(self, query: str, num_results: int) -> Optional[List[SearchResult]]:
        """Check if query is in cache and still valid"""
        cache_key = self._get_cache_key(query, num_results)
        
        if cache_key in self.cache:
            results, timestamp = self.cache[cache_key]
            
            # Check if cache is still valid
            if datetime.now() - timestamp < self.cache_ttl:
                self.stats["cache_hits"] += 1
                self._log("SEARCH", f"Cache hit for: {query[:50]}")
                return results
            else:
                # Cache expired, remove it
                del self.cache[cache_key]
        
        return None
    
    def _store_cache(self, query: str, num_results: int, results: List[SearchResult]):
        """Store results in cache"""
        cache_key = self._get_cache_key(query, num_results)
        self.cache[cache_key] = (results, datetime.now())
    
    def search(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """
        Search DuckDuckGo and return results
        
        Args:
            query: Search query
            num_results: Number of results to return (default: 5)
            
        Returns:
            List of SearchResult objects
        """
        
        self.stats["total_searches"] += 1
        self._log("SEARCH", f"Searching for: {query[:50]}...")
        
        # Check cache first
        cached = self._check_cache(query, num_results)
        if cached:
            return cached
        
        try:
            # Make request to DuckDuckGo HTML
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.post(url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            result_divs = soup.find_all('div', class_='result')
            
            for result_div in result_divs[:num_results]:
                try:
                    # Extract title and URL
                    title_tag = result_div.find('a', class_='result__a')
                    if not title_tag:
                        continue
                    
                    title = title_tag.get_text(strip=True)
                    url = title_tag.get('href', '')
                    
                    # Extract snippet
                    snippet_tag = result_div.find('a', class_='result__snippet')
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    # Only add if we have title and URL
                    if title and url:
                        results.append(SearchResult(title, url, snippet))
                
                except Exception as e:
                    self._log("SEARCH", f"Error parsing result: {e}")
                    continue
            
            self._log("SEARCH", f"Found {len(results)} results")
            self.stats["total_results"] += len(results)
            
            # Cache results
            self._store_cache(query, num_results, results)
            
            return results
        
        except requests.exceptions.Timeout:
            self.stats["failures"] += 1
            self._log("ERROR", "Search timeout")
            return []
        
        except requests.exceptions.RequestException as e:
            self.stats["failures"] += 1
            self._log("ERROR", f"Search request failed: {e}")
            return []
        
        except Exception as e:
            self.stats["failures"] += 1
            self._log("ERROR", f"Search error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def format_results(self, results: List[SearchResult], max_results: int = 5) -> str:
        """
        Format search results for display
        
        Args:
            results: List of SearchResult objects
            max_results: Maximum results to display
            
        Returns:
            Formatted string
        """
        
        if not results:
            return "No results found."
        
        lines = [f"Found {len(results)} result(s):\n"]
        
        for i, result in enumerate(results[:max_results], 1):
            lines.append(f"{i}. **{result.title}**")
            lines.append(f"   {result.url}")
            if result.snippet:
                # Limit snippet length
                snippet = result.snippet[:200] + "..." if len(result.snippet) > 200 else result.snippet
                lines.append(f"   {snippet}")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_stats(self) -> Dict:
        """Get search statistics"""
        total = self.stats["total_searches"]
        
        return {
            **self.stats,
            "cache_hit_rate": self.stats["cache_hits"] / max(total, 1),
            "success_rate": (total - self.stats["failures"]) / max(total, 1),
            "avg_results": self.stats["total_results"] / max(total, 1)
        }
    
    def clear_cache(self):
        """Clear the search cache"""
        count = len(self.cache)
        self.cache.clear()
        self._log("SEARCH", f"Cleared {count} cached queries")


# Convenience function for quick searches
def search_web(query: str, num_results: int = 5) -> List[SearchResult]:
    """
    Quick search function
    
    Args:
        query: Search query
        num_results: Number of results
        
    Returns:
        List of SearchResult objects
    """
    provider = SearchProvider()
    return provider.search(query, num_results)


if __name__ == "__main__":
    # Test the search provider
    print("Testing DuckDuckGo Search Provider\n")
    
    provider = SearchProvider()
    
    # Test search
    query = "Python programming language"
    results = provider.search(query, num_results=3)
    
    print(provider.format_results(results))
    
    # Test cache
    print("\nTesting cache (same query)...")
    results2 = provider.search(query, num_results=3)
    
    # Show stats
    print("\nStatistics:")
    stats = provider.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2%}" if value <= 1 else f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")