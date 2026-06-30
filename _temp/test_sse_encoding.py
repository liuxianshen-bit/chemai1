import requests, json, sys

resp = requests.post('http://localhost:8000/api/agent/chat/langgraph/stream',
    json={'persona':'teacher','message':'我要出题','provider':'deepseek','conversation_id':'test-enc'},
    stream=True, timeout=60)

for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith('data: '):
        continue
    payload = line[6:]
    if payload == '[DONE]':
        break
    try:
        evt = json.loads(payload)
        t = evt.get('type','?')
        if t in ('route','sub_agent_start','text','component'):
            raw = json.dumps(evt, ensure_ascii=False)
            has_cn = any(ord(c) > 127 for c in raw)
            print(f'[{t}] cn={has_cn} {raw[:150]}')
    except Exception as e:
        print(f'PARSE: {e} raw={payload[:100]}')
print('DONE')
