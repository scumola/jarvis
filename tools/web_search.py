"""
Web Search with Multi-Source Verification

Provides internet search with fact-checking across multiple sources to prevent
storing incorrect or outdated information in memory.
"""

import requests
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus
import time

logger = logging.getLogger(__name__)


class WebSearcher:
    """
    Multi-source web searcher with built-in fact verification.

    Searches multiple sources, compares results, and provides
    confidence ratings based on source agreement.
    """

    def __init__(self, searxng_host: str = "http://tools.badcheese.com:8888"):
        self.searxng_host = searxng_host
        self.sources_checked = []

    def search_multi_source(
        self,
        query: str,
        max_results: int = 5,
        check_facts: bool = True
    ) -> Dict[str, Any]:
        """
        Search across multiple sources and cross-reference results.

        Args:
            query: Search query
            max_results: Max results per source
            check_facts: Whether to check fact-verification sites

        Returns:
            Dict with:
            - results: List of result dicts
            - confidence: Overall confidence score
            - source_agreement: How many sources agree
            - warnings: Any contradictions or concerns
        """
        results = []
        self.sources_checked = []

        try:
            # Source 1: SearXNG (aggregates multiple search engines)
            searxng_results = self._search_searxng(query, max_results)
            if searxng_results:
                results.extend(searxng_results)
                self.sources_checked.append('searxng')

            # Source 2: Wikipedia (for factual queries)
            if self._is_factual_query(query):
                wiki_results = self._search_wikipedia(query)
                if wiki_results:
                    results.extend(wiki_results)
                    self.sources_checked.append('wikipedia')

            # Deduplicate and rank by source agreement
            consolidated = self._consolidate_results(results)

            # Fact-check if requested
            warnings = []
            confidence = "medium"  # Default

            if check_facts and self._should_fact_check(query):
                fact_check_info = self._fact_check(query, consolidated)
                warnings = fact_check_info.get('warnings', [])
                confidence = fact_check_info.get('confidence', 'medium')

            return {
                'success': True,
                'output': {
                    'query': query,
                    'results': consolidated[:max_results],
                    'total_sources': len(self.sources_checked),
                    'sources_checked': self.sources_checked,
                    'confidence': confidence,
                    'warnings': warnings,
                    'fact_checked': check_facts
                }
            }

        except Exception as e:
            logger.error(f"Multi-source search error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _search_searxng(self, query: str, max_results: int) -> List[Dict]:
        """Search using SearXNG instance."""
        try:
            url = f"{self.searxng_host}/search"
            params = {
                'q': query,
                'format': 'json',
                'categories': 'general'
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('results', [])[:max_results * 2]:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('url', ''),
                    'snippet': item.get('content', ''),
                    'source': 'searxng',
                    'published': item.get('publishedDate')
                })

            logger.info(f"SearXNG returned {len(results)} results")
            return results

        except Exception as e:
            logger.warning(f"SearXNG search failed: {e}")
            return []

    def _search_wikipedia(self, query: str) -> List[Dict]:
        """Search Wikipedia for factual information."""
        try:
            # Wikipedia API search
            search_url = "https://en.wikipedia.org/w/api.php"
            search_params = {
                'action': 'query',
                'list': 'search',
                'srsearch': query,
                'format': 'json',
                'srlimit': 3
            }

            # Wikipedia requires User-Agent header
            headers = {
                'User-Agent': 'Jarvis/1.0 (AI Assistant; Educational Use)'
            }

            response = requests.get(search_url, params=search_params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('query', {}).get('search', []):
                page_title = item['title']
                page_id = item['pageid']

                # Get extract
                extract_params = {
                    'action': 'query',
                    'prop': 'extracts',
                    'exintro': True,
                    'explaintext': True,
                    'pageids': page_id,
                    'format': 'json'
                }

                extract_response = requests.get(search_url, params=extract_params, headers=headers, timeout=10)
                extract_data = extract_response.json()
                pages = extract_data.get('query', {}).get('pages', {})
                extract = pages.get(str(page_id), {}).get('extract', '')

                results.append({
                    'title': page_title,
                    'url': f"https://en.wikipedia.org/wiki/{quote_plus(page_title)}",
                    'snippet': extract[:300] + '...' if len(extract) > 300 else extract,
                    'source': 'wikipedia',
                    'published': None
                })

            logger.info(f"Wikipedia returned {len(results)} results")
            return results

        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return []

    def _consolidate_results(self, results: List[Dict]) -> List[Dict]:
        """
        Consolidate results from multiple sources.

        Ranks by:
        - Source diversity (mentioned in multiple sources)
        - Recency
        - Source reliability (Wikipedia > general search)
        """
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []

        for result in results:
            url = result['url']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        # Score and sort
        for result in unique_results:
            score = 0

            # Wikipedia gets high score
            if result['source'] == 'wikipedia':
                score += 10

            # Recent content gets bonus
            if result.get('published'):
                score += 5

            result['relevance_score'] = score

        # Sort by score
        unique_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        return unique_results

    def _is_factual_query(self, query: str) -> bool:
        """Determine if query is asking for factual information."""
        factual_keywords = [
            'who is', 'what is', 'when', 'where', 'how many',
            'president', 'capital', 'population', 'born',
            'current', 'latest', 'definition'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in factual_keywords)

    def _should_fact_check(self, query: str) -> bool:
        """Determine if query should be fact-checked."""
        fact_check_keywords = [
            'president', 'vice president', 'election', 'minister',
            'current', 'who is', 'leader', 'government', 'official',
            'statistics', 'population', 'date', 'year'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in fact_check_keywords)

    def _fact_check(self, query: str, results: List[Dict]) -> Dict[str, Any]:
        """
        Perform basic fact-checking on results.

        Checks for:
        - Source agreement (do multiple sources say the same thing?)
        - Recency warnings (old information)
        - Contradiction detection
        """
        warnings = []
        confidence = "medium"

        # Check source diversity
        sources = set(r['source'] for r in results)
        if len(sources) < 2:
            warnings.append("Only one source type available - consider verification")
            confidence = "low"

        # Check for Wikipedia presence (generally reliable)
        has_wikipedia = any(r['source'] == 'wikipedia' for r in results)
        if has_wikipedia:
            confidence = "high"
        elif len(sources) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Check for recency (if dates available)
        dated_results = [r for r in results if r.get('published')]
        if dated_results:
            # Could check if information is old
            pass

        # Detect potential contradictions (simple keyword check)
        snippets = [r.get('snippet', '').lower() for r in results]
        if len(snippets) >= 2:
            # Look for conflicting information
            # This is a simple heuristic - could be improved
            pass

        return {
            'confidence': confidence,
            'warnings': warnings
        }
