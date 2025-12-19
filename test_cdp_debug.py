"""Debug CDP connection."""
import requests
import json

# Get list of targets
resp = requests.get('http://localhost:9222/json')
targets = resp.json()
print(f'Found {len(targets)} targets:')
for t in targets:
    target_type = t.get('type', 'unknown')
    title = t.get('title', 'no title')[:50]
    print(f'  - {target_type}: {title}')
    if target_type == 'page':
        ws_url = t.get('webSocketDebuggerUrl')
        print(f'    WebSocket: {ws_url}')

# Try to get DOM from first page
page_targets = [t for t in targets if t.get('type') == 'page']
if page_targets:
    ws_url = page_targets[0].get('webSocketDebuggerUrl')
    print(f'\nConnecting to: {ws_url}')
    
    import websocket
    ws = websocket.create_connection(ws_url)
    
    # Enable DOM
    ws.send(json.dumps({'id': 1, 'method': 'DOM.enable'}))
    result = ws.recv()
    print(f'DOM.enable: {result[:100]}...')
    
    # Get document
    ws.send(json.dumps({'id': 2, 'method': 'DOM.getDocument'}))
    result = ws.recv()
    print(f'DOM.getDocument: {result[:200]}...')
    
    # Get flattened document
    ws.send(json.dumps({'id': 3, 'method': 'DOM.getFlattenedDocument', 'params': {'depth': -1}}))
    result = ws.recv()
    doc = json.loads(result)
    if 'result' in doc and 'nodes' in doc['result']:
        nodes = doc['result']['nodes']
        print(f'\nTotal nodes: {len(nodes)}')
        # Count by type
        types = {}
        for n in nodes:
            node_name = n.get('nodeName', 'unknown')
            types[node_name] = types.get(node_name, 0) + 1
        print('Top node types:')
        for name, count in sorted(types.items(), key=lambda x: -x[1])[:10]:
            print(f'  {name}: {count}')
    else:
        print(f'Unexpected result: {result[:300]}')
    
    ws.close()
