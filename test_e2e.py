#!/usr/bin/env python3
"""
End-to-end test for hybrid revenue drop and refrigerator crawl
"""
import json
import requests
import sys

url = "http://ec2-13-211-236-68.ap-southeast-2.compute.amazonaws.com:8000/api/chat/stream"

# Test 1: Hybrid revenue drop
print("=" * 70)
print("TEST 1: HYBRID REVENUE DROP ANALYSIS")
print("=" * 70)

payload1 = {
    "message": "doanh thu giảm tháng này so với tháng trước, chuyện gì xảy ra?"
}

print(f"Query: {payload1['message']}\n")

try:
    response = requests.post(
        url,
        json=payload1,
        headers={"Content-Type": "application/json"},
        stream=True,
        timeout=120
    )
    
    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code}")
        print(response.text[:500])
    else:
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("event:"):
                event_type = line.split(": ")[1]
                event_count += 1
                print(f"[Event {event_count}] Type: {event_type}")
            elif line and line.startswith("data:"):
                data_str = line[6:]
                try:
                    data = json.loads(data_str)
                    if "message" in data:
                        print(f"  → {data['message']}")
                    elif "text" in data:
                        print(f"  → {data['text'][:100]}...")
                    elif "tool" in data:
                        print(f"  → tool: {data.get('tool')}")
                    else:
                        keys = list(data.keys())[:3]
                        print(f"  → {keys}")
                except:
                    print(f"  → {data_str[:80]}")
        
        print(f"\nTotal events received: {event_count}\n")

except Exception as e:
    print(f"ERROR: {e}\n")

# Test 2: Refrigerator crawl
print("=" * 70)
print("TEST 2: REFRIGERATOR CRAWL (TINYFISH DASHBOARD)")
print("=" * 70)

payload2 = {
    "message": "crawl competitor refrigerator prices from shopee tiki, show me dashboard data"
}

print(f"Query: {payload2['message']}\n")

try:
    response = requests.post(
        url,
        json=payload2,
        headers={"Content-Type": "application/json"},
        stream=True,
        timeout=180
    )
    
    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code}")
        print(response.text[:500])
    else:
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("event:"):
                event_type = line.split(": ")[1]
                event_count += 1
                print(f"[Event {event_count}] Type: {event_type}")
            elif line and line.startswith("data:"):
                data_str = line[6:]
                try:
                    data = json.loads(data_str)
                    if "message" in data:
                        print(f"  → Status: {data['message']}")
                    elif "text" in data:
                        print(f"  → Insight: {data['text'][:100]}...")
                    elif "row_count" in data:
                        print(f"  → Data rows: {data['row_count']}")
                    elif "title" in data and "type" in data:
                        print(f"  → Chart: {data['title']}")
                    elif "output_type" in data:
                        print(f"  → Output type: {data['output_type']}")
                    else:
                        keys = list(data.keys())[:3]
                        print(f"  → {keys}")
                except:
                    print(f"  → {data_str[:80]}")
        
        print(f"\nTotal events received: {event_count}\n")

except Exception as e:
    print(f"ERROR: {e}\n")
