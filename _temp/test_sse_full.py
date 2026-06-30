import requests, json

resp = requests.post('http://localhost:8000/api/agent/chat/langgraph/stream',
    json={'persona':'teacher','message':'我要出题','provider':'deepseek','conversation_id':'test-full'},
    stream=True, timeout=60)

events = []
for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith('data: '):
        continue
    payload = line[6:]
    if payload == '[DONE]':
        break
    try:
        evt = json.loads(payload)
        t = evt.get('type','?')
        events.append(t)
        if t == 'sub_agent_end':
            print(f'[sub_agent_end] agent={evt.get("agent")} display={evt.get("display")}')
        elif t == 'sub_agent_start':
            print(f'[sub_agent_start] agent={evt.get("agent")} display={evt.get("display")}')
        elif t == 'subagent_text':
            print(f'[subagent_text] {evt.get("content","")[:60]}')
        elif t == 'route':
            print(f'[route] display={evt.get("display")}')
        elif t == 'tool_call':
            print(f'[tool_call] name={evt.get("name")}')
        elif t == 'tool_result':
            print(f'[tool_result] name={evt.get("name")}')
        elif t == 'text':
            print(f'[text] {evt.get("content","")[:60]}')
        elif t == 'component':
            print(f'[component] {evt.get("component")}')
    except Exception as e:
        print(f'PARSE: {e}')

print(f'\nEvent sequence: {" → ".join(events)}')
