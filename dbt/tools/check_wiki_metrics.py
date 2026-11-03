"""Hand-calculated discovery, Wikipedia deduplication and missing-coverage check."""
import hashlib,json,subprocess,sys,tempfile,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
import duckdb
from load_fixtures import load_local
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as temp:
 p=Path(temp); rows=[]
 def listen(user,artists,day,identifier):
  rows.append({'RAW':{'user_name':user,'listened_at':int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()),'recording_msid':identifier,'track_metadata':{'track_name':identifier,'mbid_mapping':{'artist_mbids':artists,'recording_mbid':identifier}}},'_SOURCE_FILE':'hand.json','_BATCH_ID':'hand','_LOADED_AT':'2026-11-02T00:00:00Z'})
 for u,artists in {'A':['X','Y'],'B':['X','Y','Z'],'C':['X','W']}.items():
  for a in artists:listen(u,[a],'2026-10-01',u+a)
 for i,artists in enumerate([['Z'],['X'],['X','Z']]):listen('A',artists,'2026-11-01',f'future{i}')
 (p/'listens_raw.jsonl').write_text('\n'.join(map(json.dumps,rows)))
 (p/'mb_artists_raw.jsonl').write_text('\n'.join(json.dumps({'RAW':{'id':a,'name':a},'_SOURCE_FILE':'artists.json','_BATCH_ID':'hand','_LOADED_AT':'2026-11-02T00:00:00Z'}) for a in 'XYZW'))
 wiki=[]
 for artist,views,days in [('Z',10,7),('W',200,7),('Y',0,3)]:
  items=[{'timestamp':(datetime(2026,10,26)+timedelta(days=i)).strftime('%Y%m%d00'),'views':views} for i in range(days)]
  wiki.append({'RAW':{'items':items},'_SOURCE_FILE':f'wikipedia/week=2026-10-26/artist={artist}.json','_BATCH_ID':'hand','_LOADED_AT':'2026-11-02T00:00:00Z'})
 wiki.append(dict(wiki[0],_BATCH_ID='replay'))
 (p/'wiki_pageviews_raw.jsonl').write_text('\n'.join(map(json.dumps,wiki)))
 db=p/'hand.duckdb';load_local(p,str(db))
 result=subprocess.run([str(Path(sys.executable).with_name('dbt')),'build','--project-dir',str(ROOT/'dbt'),'--profiles-dir',str(ROOT/'dbt'),'--target','local','--vars','{"playlist_size":1}'],env=dict(os.environ,VAYBA_LOCAL_DB=str(db)),capture_output=True,text=True)
 assert result.returncode==0,result.stdout[-4000:]
 with duckdb.connect(str(db)) as c:
  assert c.execute("SELECT total_pageviews,observed_days FROM DEV_HUGO_SILVER.SILVER_WIKI_PAGEVIEWS WHERE artist_mbid='Z'").fetchone()==(70,7)
  discovery,lesser,coverage=c.execute('SELECT discovery_rate,lesser_known_rate,wiki_coverage_rate FROM DEV_HUGO_GOLD.METRICS_HEBDO').fetchone()
  assert abs(discovery-1/3)<1e-9,(discovery,'mixed artist listens must be counted once, conservatively')
  assert abs(lesser-.5)<1e-9 and abs(coverage-2/3)<1e-9,(lesser,coverage)
  c.execute('DELETE FROM DEV_HUGO_BRONZE.WIKI_PAGEVIEWS_RAW')
 result=subprocess.run([str(Path(sys.executable).with_name('dbt')),'build','--project-dir',str(ROOT/'dbt'),'--profiles-dir',str(ROOT/'dbt'),'--target','local','--select','silver_wiki_pageviews+'],env=dict(os.environ,VAYBA_LOCAL_DB=str(db)),capture_output=True,text=True)
 assert result.returncode==0,result.stdout[-4000:]
 with duckdb.connect(str(db)) as c:assert c.execute('SELECT lesser_known_rate,wiki_coverage_rate FROM DEV_HUGO_GOLD.METRICS_HEBDO').fetchone()==(None,0.0)
 evidence={'discovery_rate':discovery,'lesser_known_rate':lesser,'wiki_coverage_rate':coverage,'dedup_weekly_views':70,'missing_wikipedia':'NULL rate, zero coverage','result':'PASS','target':'local hand-calculated fixture'}
 (ROOT/'dbt/evidence/wiki_metrics_acceptance.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence))
