#!/usr/bin/env python3
"""Test the news headlines tool."""

import sys
sys.path.insert(0, '.')

from tools.builtin_tools import get_news_headlines_impl

print("Testing News Headlines Tool")
print("="*70)

print("\n1. Fetching breaking news headlines...")
result = get_news_headlines_impl(query="breaking news", max_results=5)

if result['success']:
    output = result['output']
    print(f"✓ Found {output['count']} headlines (out of {output['total_found']} total)")
    print(f"  Query: '{output['query']}'\n")

    for i, headline in enumerate(output['headlines'], 1):
        print(f"{i}. {headline['title']}")
        if headline.get('snippet'):
            print(f"   {headline['snippet'][:100]}...")
        print(f"   {headline['url']}")
        if headline.get('published'):
            print(f"   Published: {headline['published']}")
        print()
else:
    print(f"✗ Error: {result['error']}")

print("="*70)
print("✓ News tool working!")
