import requests, json
resp = requests.post('http://localhost:8000/api/agent/chat/langgraph/stream',
    json={'persona':'teacher','message':'高一一班有吗','provider':'deepseek','conversation_id':'test-debug2'},
    stream=True, timeout=120)

# Print ALL event types including raw names
for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith('data: '): continue
    payload = line[6:]
    if payload == '[DONE]':
        print('[DONE]')
        break
    try:
        evt = json.loads(payload)
        t = evt.get('type','?')
        if t == 'sub_agent_start':
            print(f'  SUB_START: {evt.get("agent")}')
        elif t == 'sub_agent_end':
            print(f'  SUB_END: {evt.get("agent")}')
        elif t == 'tool_call':
            print(f'  TOOL: {evt.get("name")}')
        elif t == 'tool_result':
            print(f'  TOOL_RESULT: {evt.get("name")}')
        elif t == 'subagent_text':
            pass  # too many
        elif t == 'text':
            print(f'  TEXT: {evt.get("content","")[:60]}')
        elif t == 'phase':
            print(f'  PHASE: {evt.get("phase")}')
        elif t == 'done':
            print('  DONE')
        else:
            print(f'  OTHER: {t} {json.dumps(evt,ensure_ascii=False)[:100]}')
    except Exception as e:
        print(f'  PARSE_ERROR: {e} raw={payload[:80]}')
