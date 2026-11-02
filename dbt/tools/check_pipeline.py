"""Acceptance, replay, leakage and demonstrated failure checks; local target only."""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
import duckdb
from load_fixtures import load_local
ROOT=Path(__file__).resolve().parents[2]
DBT=Path(sys.executable).with_name('dbt')
ENV=dict(os.environ, DBT_SEND_ANONYMOUS_USAGE_STATS='false', TZ='UTC')

def build(database,extra=None,success=True):
 args=[str(DBT),'build','--project-dir',str(ROOT/'dbt'),'--profiles-dir',str(ROOT/'dbt'),'--target','local','--vars',json.dumps(extra or {})]
 result=subprocess.run(args,env=dict(ENV,VAYBA_LOCAL_DB=str(database)),capture_output=True,text=True)
 if (result.returncode==0)!=success:raise AssertionError(result.stdout[-5000:]+result.stderr[-1000:])
 return result.stdout

def snapshot(database):
 with duckdb.connect(str(database),read_only=True) as c:
  return {table:c.execute(f'SELECT * FROM DEV_HUGO_GOLD.{table} ORDER BY ALL').fetchall() for table in ['PLAYLIST_HEBDO','METRICS_HEBDO']}

def main(fixtures,database):
 evidence={}
 build(database)
 before=snapshot(database)
 load_local(fixtures,str(database));build(database)
 assert snapshot(database)==before,'Replay changed business results'
 evidence['real_data_replay']='PASS'
 with duckdb.connect(str(database),read_only=True) as c:
  expected={'LISTENS_RAW':6652,'MB_ARTISTS_RAW':915}
  for table,n in expected.items():assert c.execute(f'SELECT COUNT(*) FROM DEV_HUGO_BRONZE.{table}').fetchone()[0]==n
  assert c.execute('SELECT COUNT(*) FROM DEV_HUGO_SILVER.SILVER_LISTENS').fetchone()[0]==6125
  assert c.execute('SELECT COUNT(*) FROM DEV_HUGO_SILVER.LISTEN_ARTISTS').fetchone()[0]==6615
  assert c.execute('SELECT COUNT(*) FROM DEV_HUGO_SILVER.LISTENS_QUARANTINE').fetchone()[0]==527
  assert c.execute('SELECT COUNT(DISTINCT listen_key) FROM DEV_HUGO_SILVER.train_listens').fetchone()[0]==4858
  assert c.execute("SELECT COUNT(*) FROM DEV_HUGO_SILVER.silver_listens WHERE listened_at >= TIMESTAMP '2026-10-26' AND listened_at < TIMESTAMP '2026-11-02'").fetchone()[0]==1267
  cols=[x[0] for x in c.execute('SELECT * FROM DEV_HUGO_GOLD.METRICS_HEBDO').description]
  evidence['metrics']=dict(zip(cols,c.execute('SELECT * FROM DEV_HUGO_GOLD.METRICS_HEBDO').fetchone()))
  evidence['playlist_rows']=c.execute('SELECT COUNT(*) FROM DEV_HUGO_GOLD.PLAYLIST_HEBDO').fetchone()[0]
  # Remove validation-week data in a disposable copy: recommendations must stay identical.
 with tempfile.TemporaryDirectory() as temp:
  t=Path(temp);copy=t/'without_future.duckdb';shutil.copyfile(database,copy)
  with duckdb.connect(str(copy)) as c:
   c.execute("DELETE FROM DEV_HUGO_BRONZE.LISTENS_RAW WHERE cast(json_extract_string(RAW,'$.listened_at') as bigint)>=1792972800")
  args={'test_end':'2026-10-26'}
  # Run only the playlist ancestry: no held-out completeness test is expected in this check.
  result=subprocess.run([str(DBT),'build','--project-dir',str(ROOT/'dbt'),'--profiles-dir',str(ROOT/'dbt'),'--target','local','--select','+playlist_hebdo','--exclude','window_complete'],env=dict(ENV,VAYBA_LOCAL_DB=str(copy)),capture_output=True,text=True)
  assert result.returncode==0,result.stdout[-2000:]
  assert snapshot(copy)['PLAYLIST_HEBDO']==before['PLAYLIST_HEBDO'],'Future listens influenced recommendation'
  evidence['no_temporal_leakage']='PASS'
  # Yanis's API files carry the user only in the GCS filename. Same events -> same gold.
  api=t/'api_filename.duckdb';shutil.copyfile(database,api)
  with duckdb.connect(str(api)) as c:
   c.execute("""UPDATE DEV_HUGO_BRONZE.LISTENS_RAW
    SET _SOURCE_FILE='listenbrainz/week=2026-10-26/user=' || json_extract_string(RAW,'$.user_name') || '.json',
        RAW=json_merge_patch(RAW, '{"user_name":null}')""")
  build(api)
  assert snapshot(api)==before,'API filenames changed user identities or gold results'
  evidence['api_source_filename_compatibility']='PASS: 6652 API-shaped listens produce identical gold results'
  # Known, independently calculated example: A={X,Y}, B={X,Y,Z}, C={X,W}.
  f=t/'fixtures';f.mkdir();rows=[]
  def event(user,artist,day):
   epoch=int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
   rows.append({'RAW':{'user_name':user,'listened_at':epoch,'recording_msid':f'{user}-{artist}-{day}','track_metadata':{'track_name':artist,'mbid_mapping':{'artist_mbids':[artist] if artist else [],'recording_mbid':artist}}},'_SOURCE_FILE':'hand.json','_BATCH_ID':'acceptance','_LOADED_AT':'2026-11-02T09:00:00Z'})
  for u,artists in {'A':['X','Y'],'B':['X','Y','Z'],'C':['X','W']}.items():
   for a in artists:event(u,a,'2026-10-01T12:00:00')
  event('A','Z','2026-11-01T20:00:00');event('A','','2026-10-01T13:00:00')
  (f/'listens_raw.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
  (f/'mb_artists_raw.jsonl').write_text('\n'.join(json.dumps({'RAW':{'id':a,'name':a},'_SOURCE_FILE':'hand_artists.json','_BATCH_ID':'acceptance','_LOADED_AT':'2026-11-02T09:00:00Z'}) for a in ['X','Y','Z','W']))
  hand=t/'hand.duckdb';load_local(f,str(hand));build(hand,{'playlist_size':1})
  with duckdb.connect(str(hand),read_only=True) as c:
   row=c.execute('SELECT ARTIST_MBID,SCORE FROM DEV_HUGO_GOLD.PLAYLIST_HEBDO WHERE USER_KEY=?',[hashlib.sha256(b'A').hexdigest()]).fetchone()
   assert row[0]=='Z' and abs(row[1]-2/3)<1e-9,row
   assert c.execute('SELECT COUNT(*) FROM DEV_HUGO_SILVER.LISTENS_QUARANTINE').fetchone()[0]==1
  evidence['hand_calculated_acceptance']='PASS: A -> Z; score=2/3; invalid listen quarantined'
  # Force a missing dimension key in disposable bronze. dbt must fail visibly.
  with duckdb.connect(str(hand)) as c:c.execute("DELETE FROM DEV_HUGO_BRONZE.MB_ARTISTS_RAW WHERE json_extract_string(RAW,'$.id')='Z'")
  failure=build(hand,{'playlist_size':1},success=False)
  assert 'no_unknown_artists' in failure
  evidence['injected_missing_artist']='PASS: no_unknown_artists failed as expected'
  (ROOT/'dbt/evidence/expected_failure.txt').write_text('\n'.join(s for s in failure.splitlines() if 'no_unknown_artists' in s or 'ERROR=' in s))
 build(database)
 evidence['executed_at_utc']=datetime.now(timezone.utc).isoformat();evidence['execution_target']='local DuckDB; Snowflake not executed'
 evidence['files_sha256']={name:hashlib.sha256((fixtures/name).read_bytes()).hexdigest() for name in ['listens_raw.jsonl','mb_artists_raw.jsonl']}
 (ROOT/'dbt/evidence/checks.json').write_text(json.dumps(evidence,indent=2,default=str))
 print(json.dumps(evidence,indent=2,default=str))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--database',type=Path,default=ROOT/'vayba_local.duckdb');a=p.parse_args();main(a.fixtures,a.database.resolve())
