import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\jim\Box\Downloads\logs.1769441951522.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total log entries: {len(data)}")
print("\n=== Last 80 messages ===\n")

for d in data[-80:]:
    msg = d.get('message', '')
    if msg:
        print(msg[:300])
