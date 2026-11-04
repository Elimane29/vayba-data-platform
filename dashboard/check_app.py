"""One live check: real GOLD, page callbacks, and persistent-write/bronze-read denial."""
import json
from pathlib import Path

import snowflake.connector
from app import connect, create_app, fetch_gold, render, SCHEMA


def main():
    data = fetch_gold()
    assert data['playlist'] and data['metrics']
    assert all(1 <= r['POSITION'] <= 10 for r in data['playlist'])
    app = create_app(data)
    client = app.server.test_client()
    assert client.get('/').status_code == 200
    assert client.get('/_dash-layout').status_code == 200
    week = data['playlist'][0]['WEEK_START']
    user = data['playlist'][0]['USER_KEY']
    playlist = render('playlist', week, user, data)
    assert len(playlist.children[1].children) == 10
    response = client.post('/_dash-update-component', json={
        'output': 'content.children',
        'outputs': {'id': 'content', 'property': 'children'},
        'inputs': [{'id': 'view', 'property': 'value', 'value': 'metrics'},
                   {'id': 'week', 'property': 'value', 'value': week},
                   {'id': 'profile', 'property': 'value', 'value': user},
                   {'id': 'dataset', 'property': 'data', 'value': data}],
        'state': [], 'changedPropIds': ['view.value'],
    })
    assert response.status_code == 200, response.data[:500]
    assert f"{data['metrics'][0]['HIT_RATE_S1']:.0%}" in response.get_data(as_text=True)
    denied = []
    with connect() as con, con.cursor() as cur:
        cur.execute('SELECT CURRENT_ROLE(), CURRENT_SECONDARY_ROLES()')
        role, secondary = cur.fetchone()
        assert role == 'VAYBA_DASH_READ' and not json.loads(secondary)['roles']
        for name, sql in [
            ('bronze_read', 'SELECT COUNT(*) FROM VAYBA.BRONZE.LISTENS_RAW'),
            ('persistent_gold_insert', f'INSERT INTO VAYBA.{SCHEMA}.PLAYLIST_HEBDO SELECT * FROM VAYBA.{SCHEMA}.PLAYLIST_HEBDO WHERE FALSE'),
        ]:
            try:
                cur.execute(sql)
            except snowflake.connector.ProgrammingError as e:
                denied.append({'check': name, 'denied': True, 'error_code': e.errno, 'query_id': e.sfqid})
            else:
                raise AssertionError(name + ' should be denied')
    evidence = {'role': role, 'secondary_roles': 'NONE', 'gold_rows': len(data['playlist']),
                'profiles': len({r['USER_KEY'] for r in data['playlist']}), 'playlist_view': 'PASS', 'metrics_callback': 'PASS', 'denied': denied}
    path = Path(__file__).parent / 'evidence' / 'checks.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
