import sys, os, json, time, re, urllib.request
for l in (open(os.environ['ENV_FILE']) if os.environ.get('ENV_FILE') else []):
    if '=' in l and not l.startswith('#'):
        k, v = l.strip().split('=', 1); os.environ[k] = v.strip('"\'')
os.makedirs('out', exist_ok=True)
name = sys.argv[1]
prompt = open('prompt.txt').read()

def sse(req):
    with urllib.request.urlopen(req, timeout=1800) as r:
        for line in r:
            line = line.decode().strip()
            if line.startswith('data:'):
                d = line[5:].strip()
                if d and d != '[DONE]': yield json.loads(d)

t0 = time.time(); ttft = None; text = []; usage = {}
if name.startswith('gpt'):
    body = {"model": name, "input": prompt, "stream": True}
    req = urllib.request.Request("https://api.openai.com/v1/responses", json.dumps(body).encode(),
        {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    for e in sse(req):
        if e["type"] == "response.output_text.delta":
            ttft = ttft or time.time() - t0; text.append(e["delta"])
        elif e["type"] == "response.completed": usage = e["response"]["usage"]
        elif e["type"] in ("response.failed", "error"): print(e, file=sys.stderr)
else:
    body = {"model": name, "max_tokens": 64000, "stream": True, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
        {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
    for e in sse(req):
        t = e["type"]
        if t == "message_start": usage.update(e["message"]["usage"])
        elif t == "content_block_delta" and e["delta"].get("type") == "text_delta":
            ttft = ttft or time.time() - t0; text.append(e["delta"]["text"])
        elif t == "message_delta": usage.update(e.get("usage", {})); usage["stop_reason"] = e["delta"].get("stop_reason")
        elif t == "error": print(e, file=sys.stderr)
el = time.time() - t0
raw = "".join(text)
open(f"out/{name}.raw.txt", "w").write(raw)
m = re.search(r"```html\s*\n(.*?)```", raw, re.S) or re.search(r"(<!DOCTYPE.*</html>)", raw, re.S | re.I)
open(f"out/{name}.html", "w").write(m.group(1) if m else raw)
json.dump({"model": name, "elapsed_s": round(el, 1), "ttft_s": round(ttft or 0, 1), "usage": usage, "chars": len(raw)}, open(f"out/{name}.meta.json", "w"), ensure_ascii=False, indent=1)
print(name, "done", round(el, 1), "s", usage)
