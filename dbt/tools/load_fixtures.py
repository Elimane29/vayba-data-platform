"""Load Yanis's JSONL envelopes into DEV_HUGO_BRONZE, ignoring exact replays."""
import argparse, hashlib, json, os
from pathlib import Path
TABLES={'listens_raw.jsonl':'LISTENS_RAW','mb_artists_raw.jsonl':'MB_ARTISTS_RAW','wiki_pageviews_raw.jsonl':'WIKI_PAGEVIEWS_RAW'}
def records(path):
 for n,line in enumerate(path.open(),1):
  r=json.loads(line)
  if not isinstance(r.get('RAW'),dict) or any(not r.get(k) for k in ('_SOURCE_FILE','_BATCH_ID','_LOADED_AT')):raise ValueError(f'{path.name}:{n}: invalid bronze envelope')
  yield r

def load_local(folder,database):
 import duckdb
 con=duckdb.connect(database)
 con.execute('CREATE SCHEMA IF NOT EXISTS DEV_HUGO_BRONZE')
 con.execute("SET TimeZone='UTC'")
 for name,table in TABLES.items():
  rows=list(records(folder/name)) if (folder/name).exists() else []
  if not rows and table != 'WIKI_PAGEVIEWS_RAW':raise ValueError(f'Missing or empty fixture: {name}')
  con.execute(f'CREATE TABLE IF NOT EXISTS DEV_HUGO_BRONZE.{table} (RAW JSON, _SOURCE_FILE VARCHAR, _BATCH_ID VARCHAR, _LOADED_AT TIMESTAMPTZ, _ROW_HASH VARCHAR PRIMARY KEY)')
  values=[(json.dumps(r['RAW'],sort_keys=True),r['_SOURCE_FILE'],r['_BATCH_ID'],r['_LOADED_AT'],hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()) for r in rows]
  if values:con.executemany(f'INSERT INTO DEV_HUGO_BRONZE.{table} VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING',values)
  print(table,con.execute(f'SELECT COUNT(*) FROM DEV_HUGO_BRONZE.{table}').fetchone()[0])
 con.close()

def load_snowflake(folder):
 import snowflake.connector
 args=dict(account=os.environ['SNOWFLAKE_ACCOUNT'],user=os.environ['SNOWFLAKE_USER'],database='VAYBA',warehouse=os.getenv('SNOWFLAKE_WAREHOUSE','VAYBA_WH'),role=os.getenv('SNOWFLAKE_ROLE','SYSADMIN'))
 if os.getenv('SNOWFLAKE_PRIVATE_KEY_FILE'):args['private_key_file']=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE']
 else:args['authenticator']='externalbrowser'
 with snowflake.connector.connect(**args) as con:
  cur=con.cursor();cur.execute('CREATE SCHEMA IF NOT EXISTS VAYBA.DEV_HUGO_BRONZE');cur.execute('USE SCHEMA VAYBA.DEV_HUGO_BRONZE')
  for name,table in TABLES.items():
   cur.execute(f'CREATE TABLE IF NOT EXISTS {table} (RAW VARIANT,_SOURCE_FILE VARCHAR,_BATCH_ID VARCHAR,_LOADED_AT TIMESTAMP_TZ)')
   if table == 'WIKI_PAGEVIEWS_RAW' and not (folder/name).exists():continue
   path=(folder/name).resolve();list(records(path))
   if "'" in str(path):raise ValueError('Paths containing quotes are unsupported')
   cur.execute('CREATE OR REPLACE TEMPORARY TABLE VAYBA_FIXTURE_INPUT (ENVELOPE VARIANT)')
   cur.execute(f"PUT 'file://{path}' @%VAYBA_FIXTURE_INPUT AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
   cur.execute('COPY INTO VAYBA_FIXTURE_INPUT FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT')
   cur.execute(f'''MERGE INTO {table} t USING (
    SELECT ENVELOPE:RAW AS RAW,ENVELOPE:_SOURCE_FILE::VARCHAR AS _SOURCE_FILE,
    ENVELOPE:_BATCH_ID::VARCHAR AS _BATCH_ID,ENVELOPE:_LOADED_AT::TIMESTAMP_TZ AS _LOADED_AT,
    SHA2(TO_JSON(ENVELOPE),256) AS _ROW_HASH FROM VAYBA_FIXTURE_INPUT
    QUALIFY ROW_NUMBER() OVER(PARTITION BY _ROW_HASH ORDER BY _LOADED_AT DESC)=1
    ) s ON t.RAW=s.RAW AND t._SOURCE_FILE=s._SOURCE_FILE AND t._BATCH_ID=s._BATCH_ID AND t._LOADED_AT=s._LOADED_AT WHEN NOT MATCHED THEN
    INSERT(RAW,_SOURCE_FILE,_BATCH_ID,_LOADED_AT) VALUES(s.RAW,s._SOURCE_FILE,s._BATCH_ID,s._LOADED_AT)''')
   cur.execute(f'SELECT COUNT(*) FROM {table}');print(table,cur.fetchone()[0],'query_id',cur.sfqid)
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixtures',type=Path,required=True);parser.add_argument('--target',choices=['local','snowflake'],default='local');parser.add_argument('--database',default='vayba_local.duckdb');a=parser.parse_args()
 if a.target=='local':load_local(a.fixtures,a.database)
 else:load_snowflake(a.fixtures)
