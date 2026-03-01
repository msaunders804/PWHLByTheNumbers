import requests, json
r = requests.get('https://lscluster.hockeytech.com/feed/index.php', params={
    'feed': 'gc', 'tab': 'gamesummary', 'game_id': 210,
    'key': '446521baf8c38984', 'client_code': 'pwhl', 'fmt': 'json'
})
gs = r.json()['GC']['Gamesummary']
print(json.dumps(list(gs['goalies'].keys()), indent=2))