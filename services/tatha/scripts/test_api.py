"""测试 Tatha API - 全链路（LLM意图 + RAG检索 + LLM推荐）"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8010"

def test(endpoint, data=None, token="fresh-token-deepseek-test"):
    url = f"{BASE}{endpoint}"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}"
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            print(f"\n=== {endpoint} ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result
    except urllib.error.HTTPError as e:
        print(f"\n=== {endpoint} ERROR {e.code} ===")
        print(e.read().decode())
        return None

# 1. 诗词推荐 - 思乡
print("\n" + "="*60)
print("测试 1: 推荐一句思乡的诗")
print("="*60)
test("/v1/ask", {"message": "推荐一句思乡的诗"})

# 2. 诗词推荐 - 送别
print("\n" + "="*60)
print("测试 2: 送别的诗")
print("="*60)
test("/v1/ask", {"message": "来一首送别的古诗"})

# 3. 诗词推荐 - 励志
print("\n" + "="*60)
print("测试 3: 励志的诗")
print("="*60)
test("/v1/ask", {"message": "给我推荐一句励志的诗"})
