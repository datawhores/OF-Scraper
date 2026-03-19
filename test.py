import json
import urllib.request

# --- 1. PASTE YOUR TEST DATA HERE ---
WEBHOOK_URL = "https://discord.com/api/webhooks/1484200423412858960/EYB1_3e8gJxnvFPoYj4nfO5ST-cfH2z4S56yJyh-1QDbcGV7lLHZDgAqgCB1LSl5b0OO"
VERSION = "3.14.5"
BODY = """### 🐛 Bug Fixes
* Testing the Discord webhook payload.
* Let's see if this successfully posts to the channel!
"""

# --- 2. THE EXACT LOGIC FROM YOUR GITHUB ACTION ---
print(f"Preparing payload for Version: {VERSION}...")

clean_ver = VERSION.lstrip('v')
content = f'# Release {clean_ver}\n{BODY}'

# Truncate if too long
if len(content) > 1900:
    content = content[:1900] + '\n\n... [Changelog Truncated]'

if WEBHOOK_URL and WEBHOOK_URL.startswith("http"):
    print("Sending request to Discord...")
    data = json.dumps({'content': content}).encode('utf-8')
    req = urllib.request.Request(
        WEBHOOK_URL, 
        data=data, 
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    
    try:
        response = urllib.request.urlopen(req)
        # Discord usually returns a 204 No Content on a successful webhook post
        print(f"✅ Success! Discord responded with status code: {response.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} - {e.reason}")
        print(e.read().decode('utf-8')) # This will print Discord's exact complaint
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("⚠️ Webhook URL is missing or invalid.")