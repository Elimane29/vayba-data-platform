"""Check the actual neighbors model against independent counts, including stable ties."""
import json
from pathlib import Path
from jinja2 import Environment, StrictUndefined
import duckdb
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'dbt/models/gold/neighbors.sql').read_text()
sql=Environment(undefined=StrictUndefined).from_string(source).render(ref=lambda _: 'user_artists')
rows=[('A','a_low',1),('A','z_high',5),('A','m_tied',5),
      ('B','a_low',8),('B','z_high',3),('B','m_tied',2)]
with duckdb.connect() as c:
 c.execute('CREATE TABLE user_artists(user_key VARCHAR,artist_mbid VARCHAR,listens BIGINT)')
 c.executemany('INSERT INTO user_artists VALUES (?,?,?)',rows)
 result=c.execute(sql+' ORDER BY user_key,neighbor_key').fetchall()
 by_pair={(r[0],r[1]):r for r in result}
 assert by_pair['A','B'][3]=='z_high',result
 assert by_pair['B','A'][3]=='a_low',result
 assert all(r[2]==3 and r[4]==1 for r in result),result
 c.execute('DELETE FROM user_artists');c.executemany('INSERT INTO user_artists VALUES (?,?,?)',list(reversed(rows)))
 assert c.execute(sql+' ORDER BY user_key,neighbor_key').fetchall()==result
 c.execute("UPDATE user_artists SET listens=3 WHERE user_key='B' AND artist_mbid='m_tied'")
 assert c.execute(sql+" ORDER BY user_key,neighbor_key").fetchall()[0][3]=='m_tied'
evidence={'result':'PASS','actual_model':'neighbors.sql','rule':'target listener plays DESC, neighbor plays DESC, artist MBID ASC','most_listened_shared_artist':'z_high','reciprocal_reason':'a_low','lexical_tie_break':'m_tied','common_artists':3,'similarity':1.0,'insertion_order_independent':True}
(ROOT/'dbt/evidence/reasons_acceptance.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence))
