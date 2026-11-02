"""Local Dash viewer: only GOLD is queried, under a read-only Snowflake role."""
import json
import logging
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from dash import Dash, Input, Output, State, dcc, html, no_update
import plotly.graph_objects as go
import snowflake.connector
from snowflake.connector import DictCursor

ROOT = Path(__file__).resolve().parent
TEXT = json.loads((ROOT / 'ui_text.json').read_text(encoding='utf-8'))
ROLE = 'VAYBA_DASH_READ'
SCHEMA = os.environ.get('VAYBA_GOLD_SCHEMA', 'DEV_HUGO_DBT_GOLD').upper()
if not re.fullmatch(r'[A-Z][A-Z0-9_]*', SCHEMA):
    raise ValueError('Invalid VAYBA_GOLD_SCHEMA')


def connect():
    connection = snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'], user=os.environ['SNOWFLAKE_USER'],
        private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE'], role=ROLE,
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE', 'VAYBA_WH'), database='VAYBA',
        schema=SCHEMA, session_parameters={'QUERY_TAG': 'vayba-dash-readonly', 'TIMEZONE': 'UTC'},
    )
    connection.cursor().execute('USE SECONDARY ROLES NONE')
    return connection


def fetch_gold():
    def value(v):
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return float(v) if isinstance(v, Decimal) else v

    with connect() as connection, connection.cursor(DictCursor) as cursor:
        data = {}
        for name, columns, order in [
            ('playlist', 'WEEK_START,USER_KEY,POSITION,RECORDING_MBID,TRACK_NAME,ARTIST_MBID,ARTIST_NAME,BECAUSE_ARTIST_NAME,SCORE', 'WEEK_START DESC,USER_KEY,POSITION'),
            ('metrics', 'WEEK_START,USERS_EVALUATED,HIT_RATE_S1,HIT_RATE_BASELINE_S1,DISCOVERY_RATE,LAST_LOADED_AT', 'WEEK_START DESC'),
        ]:
            table = 'PLAYLIST_HEBDO' if name == 'playlist' else 'METRICS_HEBDO'
            # ponytail: 10,000 rows cover the prototype; paginate for a larger deployment.
            cursor.execute(f'SELECT {columns} FROM VAYBA.{SCHEMA}.{table} ORDER BY {order} LIMIT 10000')
            data[name] = [{key: value(v) for key, v in row.items()} for row in cursor.fetchall()]
        return data


def profiles(data, week):
    keys = sorted({row['USER_KEY'] for row in data['playlist'] if row['WEEK_START'] == week})
    return [{'label': f"{TEXT['profile']} {i + 1}", 'value': key} for i, key in enumerate(keys)]


def card(label, value, caption):
    return html.Div([html.P(label, className='eyebrow'), html.Strong(value), html.P(caption)], className='card')


def render(view, week, user, data):
    if not week:
        return html.P(TEXT['empty'])
    if view == 'playlist':
        rows = [r for r in data['playlist'] if r['WEEK_START'] == week and r['USER_KEY'] == user]
        return html.Section([
            html.Div([html.H2(TEXT['playlist_title']), html.P(TEXT['playlist_intro'])], className='section-head'),
            html.Ol([
                html.Li([
                    html.Span(f"{int(r['POSITION']):02}", className='position'),
                    html.Div([html.H3(r['TRACK_NAME']), html.P(r['ARTIST_NAME'], className='artist')]),
                    html.P([html.Span(TEXT['because']), ' ', r['BECAUSE_ARTIST_NAME']], className='reason'),
                ], className='track') for r in sorted(rows, key=lambda r: r['POSITION'])
            ], className='tracks'),
        ]) if rows else html.P(TEXT['empty'])
    metric = next((r for r in data['metrics'] if r['WEEK_START'] == week), None)
    if metric is None:
        return html.P(TEXT['empty'])
    rate = float(metric['HIT_RATE_S1'] or 0)
    baseline = float(metric['HIT_RATE_BASELINE_S1'] or 0)
    figure = go.Figure(go.Bar(
        x=[rate, baseline], y=[TEXT['colistening'], TEXT['popularity']], orientation='h',
        marker_color=['#007f73', '#24364b'], text=[f'{rate:.0%}', f'{baseline:.0%}'], textposition='outside',
    ))
    figure.update_layout(xaxis={'range': [0, 1.12], 'tickformat': '.0%'}, yaxis={'autorange': 'reversed'},
                         margin={'l': 100, 'r': 45, 't': 20, 'b': 35}, height=230,
                         paper_bgcolor='white', plot_bgcolor='white', font={'family': 'Arial', 'color': '#24364b'})
    loaded = datetime.fromisoformat(metric['LAST_LOADED_AT']).astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M UTC') if metric['LAST_LOADED_AT'] else '—'
    return html.Section([
        html.Div([html.H2(TEXT['metrics_title']), html.P(TEXT['metrics_intro'])], className='section-head'),
        html.Div([
            card(TEXT['evaluated'], str(metric['USERS_EVALUATED']), TEXT['evaluated_caption']),
            card(TEXT['hit_rate'], f'{rate:.0%}', TEXT['hit_caption']),
            card(TEXT['baseline'], f'{baseline:.0%}', TEXT['baseline_caption']),
            card(TEXT['discovery'], f"{float(metric['DISCOVERY_RATE'] or 0):.0%}", TEXT['discovery_caption']),
        ], className='cards'),
        html.Div([html.H3(TEXT['comparison']), dcc.Graph(figure=figure, config={'displayModeBar': False})], className='chart'),
        html.P(TEXT['sample_limit'], className='note'),
        html.P([TEXT['loaded_at'], ' ', loaded], className='loaded'),
    ])


def create_app(snapshot=None):
    data = fetch_gold() if snapshot is None else snapshot
    weeks = sorted({r['WEEK_START'] for r in data['playlist']} | {r['WEEK_START'] for r in data['metrics']}, reverse=True)
    week = weeks[0] if weeks else None
    options = profiles(data, week)
    user = options[0]['value'] if options else None
    app = Dash(__name__, assets_folder=str(ROOT / 'assets'), title='Vayba | New Vibes')
    app.layout = html.Main([
        dcc.Store(id='dataset', data=data),
        html.Header([html.Div([html.Strong('vayba', className='brand'), html.Span('NEW VIBES', className='wordmark')]),
                     html.Button(TEXT['refresh'], id='refresh', n_clicks=0)], className='topbar'),
        html.Div([html.P(TEXT['overline'], className='eyebrow'), html.H1(TEXT['headline']), html.P(TEXT['intro'])], className='hero'),
        html.Div([
            html.Div([html.Label(TEXT['week'], htmlFor='week'), dcc.Dropdown(id='week', options=[{'label': w, 'value': w} for w in weeks], value=week, clearable=False)], className='filter'),
            html.Div([html.Label(TEXT['profile_label'], htmlFor='profile'), dcc.Dropdown(id='profile', options=options, value=user, clearable=False)], className='filter'),
            html.P(TEXT['ready'], id='status', role='status'),
        ], className='filters'),
        dcc.Tabs(id='view', value='playlist', children=[dcc.Tab(label=TEXT['playlist_tab'], value='playlist'), dcc.Tab(label=TEXT['metrics_tab'], value='metrics')], className='tabs'),
        html.Div(render('playlist', week, user, data), id='content'),
        html.Footer(TEXT['footer']),
    ], className='page')

    @app.callback(Output('dataset', 'data'), Output('status', 'children'), Input('refresh', 'n_clicks'), prevent_initial_call=True)
    def refresh(_):
        try:
            return fetch_gold(), TEXT['refreshed']
        except Exception:
            logging.exception('GOLD refresh failed')
            return no_update, TEXT['refresh_error']

    @app.callback(Output('profile', 'options'), Output('profile', 'value'), Input('week', 'value'), Input('dataset', 'data'), State('profile', 'value'))
    def choose_profile(selected_week, snapshot, selected_user):
        options = profiles(snapshot, selected_week)
        return options, selected_user if any(x['value'] == selected_user for x in options) else (options[0]['value'] if options else None)

    @app.callback(Output('content', 'children'), Input('view', 'value'), Input('week', 'value'), Input('profile', 'value'), Input('dataset', 'data'))
    def show(view, selected_week, selected_user, snapshot):
        return render(view, selected_week, selected_user, snapshot)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', '8050')), debug=False)
