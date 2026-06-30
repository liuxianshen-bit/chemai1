import requests, json
resp = requests.post('http://localhost:8000/api/agent/chat/langgraph/stream',
    json={'persona':'teacher','message':'高一一班有吗','provider':'deepseek','conversation_id':'test-hang'},
    stream=True, timeout=120)

events = []
for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith('data: '): continue
    payload = line[6:]
    if payload == '[DONE]': break
    try:
        evt = json.loads(payload)
        events.append(evt.get('type','?'))
        if evt.get('type') in ('route','sub_agent_start','sub_agent_end','tool_call','tool_result','text','error','done','subagent_text'):
            print(f"[{evt.get('type')}] {json.dumps(evt, ensure_ascii=False)[:120]}")
    except: pass

print(f'\nFlow: {" → ".join(events)}')
