#!/usr/bin/env python3
"""
Диагностика voice speaker identification.

Использование:
  python3 debug_voice.py <username> <password>

Проверяет:
  1. Есть ли зарегистрированные голосовые профили в Qdrant
  2. Есть ли у текущего пользователя голосовой профиль
  3. Можно ли достать координаты (embedding)
  4. Тестовый вызов search_speaker (если есть профиль)
"""

import sys
import requests
import json

BASE = "http://localhost:8000"

def req(method, path, **kwargs):
    url = f"{BASE}{path}"
    r = requests.request(method, url, **kwargs)
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, r.text


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 debug_voice.py <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    print("=" * 60)
    print("  DIAGNOSTIC: Voice Speaker Identification")
    print("=" * 60)

    # 1. Login
    print("\n[1] Login...")
    status, data = req("POST", "/auth/login", json={"username": username, "password": password})
    if status != 200:
        print(f"  ❌ Login failed ({status}): {data}")
        sys.exit(1)
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  ✅ Logged in as {data.get('full_name', username)}")

    # 2. Voice stats (public)
    print("\n[2] Voice stats (Qdrant)...")
    status, data = req("GET", "/voice/stats")
    print(f"  {'✅' if status == 200 else '❌'} ({status}): {data}")

    # 3. Enrolled speakers
    print("\n[3] Enrolled speakers list...")
    status, data = req("GET", "/voice/enrolled-speakers")
    if status == 200:
        speakers = data.get("speakers", [])
        print(f"  {'✅' if speakers else '⚠️'} Found {data.get('count', 0)} enrolled speaker(s):")
        for s in speakers:
            print(f"      - {s['full_name']} (has_embedding: {s['has_embedding']})")
    else:
        print(f"  ❌ ({status}): {data}")

    # 4. My voice profile
    print("\n[4] My voice profile...")
    status, data = req("GET", "/voice/profile", headers=headers)
    if status == 200:
        if data.get("has_profile"):
            print(f"  ✅ Voice profile exists")
            print(f"     created_at: {data.get('created_at')}")
            print(f"     embedding_dim: {data.get('embedding_dim')}")
        else:
            print(f"  ⚠️ No voice profile for this user")
            print("     → Record your voice via frontend Profile page")
    else:
        print(f"  ❌ ({status}): {data}")

    # 5. Check latest tasks for speaker identification logs
    print("\n[5] Recent tasks (check if pipeline ran)...")
    status, data = req("GET", "/tasks?limit=5", headers=headers)
    if status == 200:
        tasks = data.get("tasks", [])
        if tasks:
            for t in tasks:
                status_str = t.get("status", "?")
                step = t.get("step", "?")
                task_id = t.get("id", "?")[:12]
                icon = "✅" if status_str == "completed" else "❌" if status_str == "failed" else "⏳"
                print(f"  {icon} {task_id}... status={status_str}, step={step}")
        else:
            print("  ⚠️ No tasks found")
    else:
        print(f"  ❌ ({status}): {data}")

    # 6. Direct Qdrant test (if profile exists)
    print("\n[6] Qdrant connectivity test...")
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections().collections
        names = [c.name for c in collections]
        if "voice_profiles" in names:
            info = client.get_collection("voice_profiles")
            print(f"  ✅ Collection 'voice_profiles' exists, points: {info.points_count}")
        else:
            print(f"  ⚠️ Collection 'voice_profiles' not found. Available: {names}")
    except ImportError:
        print("  ⚠️ qdrant-client not installed locally, skipping")
    except Exception as e:
        print(f"  ❌ Qdrant error: {e}")

    print("\n" + "=" * 60)
    print("  Done. If you see ❌ or ⚠️ above, that's the issue.")
    print("=" * 60)


if __name__ == "__main__":
    main()
