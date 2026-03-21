#!/usr/bin/env python
"""Test script to verify Dify API integration."""

import asyncio
import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from backend.api.routes.chat_router import _process_with_dify, _stream_sse_event


async def test_dify():
    """Test Dify API with actual message."""
    print("=" * 60)
    print("Testing Dify API Integration")
    print("=" * 60)
    
    # Load env
    from dotenv import load_dotenv
    load_dotenv()
    
    DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
    DIFY_API_URL = os.getenv("DIFY_API_URL", "")
    
    print(f"\n📋 Configuration:")
    print(f"  DIFY_API_URL: {DIFY_API_URL}")
    print(f"  DIFY_API_KEY: {DIFY_API_KEY[:20]}...")
    print(f"  Key type: {'✅ app-key' if DIFY_API_KEY.startswith('app-') else '❌ not app-key'}")
    
    if not DIFY_API_KEY or DIFY_API_KEY.startswith("dataset-"):
        print("\n❌ DIFY_API_KEY is not valid app-key!")
        return
    
    print("\n🔄 Testing chat stream...")
    print("-" * 60)
    
    message = "Tổng doanh thu bao nhiêu?"
    async for event in _process_with_dify(message, None, "test_user"):
        print(f"Event received: {event[:100]}...")
        if "message_complete" in event or "error" in event:
            print(event)
            break
    
    print("-" * 60)
    print("\n✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(test_dify())
