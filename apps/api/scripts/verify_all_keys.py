import os
import urllib.request
import urllib.error
import json
from dotenv import load_dotenv

load_dotenv()

# We will test an actual completion endpoint rather than just the models endpoint
# to definitively prove the key works for generation.

def test_gemini_generation(key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    data = json.dumps({
        "contents": [{"parts": [{"text": "Reply with 'OK'"}]}]
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        if "candidates" in result:
            return True, result["candidates"][0]["content"]["parts"][0]["text"].strip()
        return False, "Unexpected response format"
    except urllib.error.URLError as e:
        return False, str(e)

def test_groq_generation(key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    data = json.dumps({
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": "Reply with 'OK'"}],
        "max_tokens": 10
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    })
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        if "choices" in result:
            return True, result["choices"][0]["message"]["content"].strip()
        return False, "Unexpected response format"
    except urllib.error.URLError as e:
        return False, str(e)

def test_openrouter_generation(key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    data = json.dumps({
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Reply with 'OK'"}],
        "max_tokens": 10
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    })
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        if "choices" in result:
            return True, result["choices"][0]["message"]["content"].strip()
        return False, "Unexpected response format"
    except urllib.error.URLError as e:
        return False, str(e)


def main():
    print("--- FULL LLM GENERATION TEST ---")
    
    openrouter_keys = [k for k in os.environ.get("OPENROUTER_KEYS", "").split(",") if k]
    gemini_keys = [k for k in os.environ.get("GEMINI_KEYS", "").split(",") if k]
    groq_keys = [k for k in os.environ.get("GROQ_KEYS", "").split(",") if k]
    
    print("\nTesting Gemini Keys:")
    for i, key in enumerate(gemini_keys):
        success, msg = test_gemini_generation(key)
        print(f"  Key {i+1} ({key[:8]}...): {'✅ PASS' if success else '❌ FAIL'} (Response: {msg})")
        
    print("\nTesting Groq Keys:")
    for i, key in enumerate(groq_keys):
        success, msg = test_groq_generation(key)
        print(f"  Key {i+1} ({key[:8]}...): {'✅ PASS' if success else '❌ FAIL'} (Response: {msg})")
        
    print("\nTesting OpenRouter Keys:")
    for i, key in enumerate(openrouter_keys):
        success, msg = test_openrouter_generation(key)
        print(f"  Key {i+1} ({key[:8]}...): {'✅ PASS' if success else '❌ FAIL'} (Response: {msg})")

if __name__ == "__main__":
    main()
