USE ROLE SYSADMIN;

USE WAREHOUSE VAYBA_WH;

COPY INTO VAYBA.DEV_HUGO_BRONZE.LISTENS_RAW FROM (SELECT $1:RAW, $1:_SOURCE_FILE::VARCHAR, $1:_BATCH_ID::VARCHAR, $1:_LOADED_AT::TIMESTAMP_TZ FROM @VAYBA.DEV_HUGO_BRONZE.FIXTURE_STAGE) PATTERN='.*listens_raw[.]jsonl([.]gz)?' FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT;
COPY INTO VAYBA.DEV_HUGO_BRONZE.MB_ARTISTS_RAW FROM (SELECT $1:RAW, $1:_SOURCE_FILE::VARCHAR, $1:_BATCH_ID::VARCHAR, $1:_LOADED_AT::TIMESTAMP_TZ FROM @VAYBA.DEV_HUGO_BRONZE.FIXTURE_STAGE) PATTERN='.*mb_artists_raw[.]jsonl([.]gz)?' FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT;


ALTER SESSION SET TIMEZONE='UTC';

ALTER SESSION SET QUERY_TAG='vayba-hugo-step1-5';

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.listens_checked AS
with parsed as (
 select
  nullif(RAW:user_name::varchar, '')
 as user_name,
  try_cast(nullif(RAW:listened_at::varchar, '')
 as bigint) as listened_epoch,
  nullif(RAW:recording_msid::varchar, '')
 as recording_msid,
  nullif(RAW:track_metadata:mbid_mapping:recording_mbid::varchar, '')
 as recording_mbid,
  nullif(RAW:track_metadata:track_name::varchar, '')
 as track_name,
  RAW:track_metadata:mbid_mapping:artist_mbids
 as artist_mbids,
  sha2(_source_file, 256) as _source_file, _batch_id, _loaded_at
 from VAYBA.DEV_HUGO_BRONZE.LISTENS_RAW
), checked as (
 select *,
  sha2(coalesce(user_name, ''), 256) as user_key,
  sha2(coalesce(user_name, '') || '|' || coalesce(cast(listened_epoch as varchar), '') || '|' || coalesce(recording_msid, ''), 256) as listen_key,
  case when user_name is null then 'missing_user'
       when listened_epoch is null or listened_epoch < 0 or listened_epoch > 4102444800 then 'invalid_timestamp'
       when recording_msid is null then 'missing_recording_msid'
       when coalesce(array_size(artist_mbids), 0) = 0 then 'missing_artist_mbid'
       else null end as rejection_reason
 from parsed
)
select * exclude (user_name) from checked
qualify row_number() over (partition by listen_key order by _loaded_at desc, _batch_id desc, _source_file desc,
 coalesce(recording_mbid, ''), coalesce(track_name, ''), cast(artist_mbids as varchar)) = 1;

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.silver_listens AS
select listen_key, user_key, to_timestamp_ntz(listened_epoch) as listened_at,
 recording_msid, recording_mbid, track_name, artist_mbids, _source_file, _batch_id, _loaded_at
from VAYBA.DEV_HUGO_SILVER.listens_checked where rejection_reason is null;

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.listen_artists AS
select distinct l.listen_key, l.user_key, l.listened_at, l.recording_mbid, l.track_name,
 nullif(a.value::varchar, '') as artist_mbid
from VAYBA.DEV_HUGO_SILVER.silver_listens l,
lateral flatten(input => l.artist_mbids) a

where artist_mbid is not null;

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.silver_artists AS
select nullif(RAW:id::varchar, '')
 as artist_mbid, nullif(RAW:name::varchar, '')
 as artist_name,
 nullif(RAW:country::varchar, '')
 as country, _loaded_at
from VAYBA.DEV_HUGO_BRONZE.MB_ARTISTS_RAW
qualify row_number() over (partition by artist_mbid order by _loaded_at desc, _source_file desc, cast(RAW as varchar)) = 1;

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.train_listens AS
select * from VAYBA.DEV_HUGO_SILVER.listen_artists
where listened_at >= cast('2026-09-21' as timestamp)
 and listened_at < cast('2026-10-26' as timestamp);

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.user_artists AS
select user_key, artist_mbid, count(*) as listens
from VAYBA.DEV_HUGO_SILVER.train_listens group by user_key, artist_mbid;

CREATE OR REPLACE VIEW VAYBA.DEV_HUGO_SILVER.listens_quarantine AS
select * from VAYBA.DEV_HUGO_SILVER.listens_checked where rejection_reason is not null;

CREATE OR REPLACE TABLE VAYBA.DEV_HUGO_GOLD.neighbors AS
with sizes as (
 select user_key, count(*) as n from VAYBA.DEV_HUGO_SILVER.user_artists group by user_key
), common as (
 select a.user_key, b.user_key as neighbor_key, count(*) as common_artists,
 min(a.artist_mbid) as because_artist_mbid
 from VAYBA.DEV_HUGO_SILVER.user_artists a join VAYBA.DEV_HUGO_SILVER.user_artists b
 on a.artist_mbid = b.artist_mbid and a.user_key <> b.user_key
 group by a.user_key, b.user_key
)
select c.*, 1.0 * common_artists / (a.n + b.n - common_artists) as similarity
from common c join sizes a on c.user_key = a.user_key join sizes b on c.neighbor_key = b.user_key;

CREATE OR REPLACE TABLE VAYBA.DEV_HUGO_GOLD.ranked_artists AS
with popularity as (
 select artist_mbid, count(distinct user_key) as users, count(*) as plays
 from VAYBA.DEV_HUGO_SILVER.train_listens group by artist_mbid
), contributions as (
 select n.user_key, a.artist_mbid, n.similarity, n.because_artist_mbid,
 row_number() over (partition by n.user_key, a.artist_mbid order by n.similarity desc, n.neighbor_key) as rn
 from VAYBA.DEV_HUGO_GOLD.neighbors n join VAYBA.DEV_HUGO_SILVER.user_artists a on n.neighbor_key = a.user_key
 where not exists (select 1 from VAYBA.DEV_HUGO_SILVER.user_artists seen where seen.user_key=n.user_key and seen.artist_mbid=a.artist_mbid)
), scores as (
 select user_key, artist_mbid, sum(similarity) as score,
 max(case when rn=1 then because_artist_mbid end) as because_artist_mbid
 from contributions group by user_key, artist_mbid
), pool as (
 select u.user_key, p.artist_mbid, p.users, p.plays, s.score, s.because_artist_mbid
 from (select distinct user_key from VAYBA.DEV_HUGO_SILVER.user_artists) u cross join popularity p
 left join scores s on s.user_key=u.user_key and s.artist_mbid=p.artist_mbid
 where not exists (select 1 from VAYBA.DEV_HUGO_SILVER.user_artists seen where seen.user_key=u.user_key and seen.artist_mbid=p.artist_mbid)
)
select *, row_number() over(partition by user_key order by case when score is null then 1 else 0 end, score desc, users desc, plays desc, artist_mbid) as recommendation_rank,
 row_number() over(partition by user_key order by users desc, plays desc, artist_mbid) as baseline_rank
from pool;

CREATE OR REPLACE TABLE VAYBA.DEV_HUGO_GOLD.playlist_hebdo AS
with tracks as (
 select artist_mbid, recording_mbid, min(track_name) as track_name, count(*) as plays
 from VAYBA.DEV_HUGO_SILVER.train_listens where recording_mbid is not null and track_name is not null
 group by artist_mbid, recording_mbid
), representative as (
 select * from tracks qualify row_number() over(partition by artist_mbid order by plays desc, recording_mbid) = 1
)
select cast('2026-10-26' as date) as week_start, r.user_key,
 cast(r.recommendation_rank as integer) as position, t.recording_mbid, t.track_name,
 r.artist_mbid, a.artist_name,
 case when r.score is null then 'Popularité (secours)' else b.artist_name end as because_artist_name,
 coalesce(r.score, 0.0) as score
from VAYBA.DEV_HUGO_GOLD.ranked_artists r join representative t on r.artist_mbid=t.artist_mbid
join VAYBA.DEV_HUGO_SILVER.silver_artists a on r.artist_mbid=a.artist_mbid
left join VAYBA.DEV_HUGO_SILVER.silver_artists b on r.because_artist_mbid=b.artist_mbid
where r.recommendation_rank <= 10;

CREATE OR REPLACE TABLE VAYBA.DEV_HUGO_GOLD.evaluation_users AS
with future as (
 select distinct user_key, artist_mbid from VAYBA.DEV_HUGO_SILVER.listen_artists
 where listened_at >= cast('2026-10-26' as timestamp)
 and listened_at < cast('2026-11-02' as timestamp)
), eligible as (
 select distinct u.user_key from VAYBA.DEV_HUGO_SILVER.user_artists u join future f on u.user_key=f.user_key
), recommendations as (
 select user_key, artist_mbid from VAYBA.DEV_HUGO_GOLD.playlist_hebdo
), baseline as (
 select user_key, artist_mbid from VAYBA.DEV_HUGO_GOLD.ranked_artists where baseline_rank <= 10
), hits as (
 select distinct r.user_key from recommendations r join future f on r.user_key=f.user_key and r.artist_mbid=f.artist_mbid
), baseline_hits as (
 select distinct b.user_key from baseline b join future f on b.user_key=f.user_key and b.artist_mbid=f.artist_mbid
)
select e.user_key,
 case when h.user_key is not null then 1 else 0 end as hit,
 case when b.user_key is not null then 1 else 0 end as baseline_hit
from eligible e left join hits h on e.user_key=h.user_key
left join baseline_hits b on e.user_key=b.user_key;

CREATE OR REPLACE TABLE VAYBA.DEV_HUGO_GOLD.metrics_hebdo AS
select cast('2026-10-26' as date) as week_start,
 count(*) as users_evaluated, avg(1.0 * hit) as hit_rate_s1, avg(1.0 * baseline_hit) as hit_rate_baseline_s1,
 (select avg(case when seen.artist_mbid is not null then 0.0 else 1.0 end) from VAYBA.DEV_HUGO_GOLD.playlist_hebdo p left join VAYBA.DEV_HUGO_SILVER.user_artists seen on seen.user_key=p.user_key and seen.artist_mbid=p.artist_mbid) as discovery_rate,
 (select max(_loaded_at) from VAYBA.DEV_HUGO_BRONZE.LISTENS_RAW) as last_loaded_at
from VAYBA.DEV_HUGO_GOLD.evaluation_users;

CREATE OR REPLACE TABLE VAYBA.DEV_HUGO_OPS.QUALITY_RESULTS AS
SELECT 'no_known_artist_recommended' AS CHECK_NAME, COUNT(*) AS FAILURES FROM (select p.* from VAYBA.DEV_HUGO_GOLD.playlist_hebdo p join VAYBA.DEV_HUGO_SILVER.user_artists u on p.user_key=u.user_key and p.artist_mbid=u.artist_mbid)
UNION ALL
SELECT 'no_unknown_artists' AS CHECK_NAME, COUNT(*) AS FAILURES FROM (select l.artist_mbid from VAYBA.DEV_HUGO_SILVER.listen_artists l left join VAYBA.DEV_HUGO_SILVER.silver_artists a on l.artist_mbid=a.artist_mbid where a.artist_mbid is null)
UNION ALL
SELECT 'playlist_grain' AS CHECK_NAME, COUNT(*) AS FAILURES FROM (select week_start,user_key,position from VAYBA.DEV_HUGO_GOLD.playlist_hebdo group by week_start,user_key,position having count(*)<>1)
UNION ALL
SELECT 'valid_rates' AS CHECK_NAME, COUNT(*) AS FAILURES FROM (select * from VAYBA.DEV_HUGO_GOLD.metrics_hebdo where users_evaluated=0 or hit_rate_s1 not between 0 and 1 or hit_rate_baseline_s1 not between 0 and 1 or discovery_rate<>1)
UNION ALL
SELECT 'window_complete' AS CHECK_NAME, COUNT(*) AS FAILURES FROM (select 1 as incomplete
where (select count(*) from VAYBA.DEV_HUGO_SILVER.silver_listens where listened_at >= cast('2026-09-21' as timestamp) and listened_at < cast('2026-10-26' as timestamp)) = 0
or (select max(listened_at) from VAYBA.DEV_HUGO_SILVER.silver_listens) < cast('2026-11-02' as timestamp) - interval '1 day')
UNION ALL
SELECT 'unique_SILVER_LISTENS',COUNT(*) FROM (SELECT LISTEN_KEY FROM VAYBA.DEV_HUGO_SILVER.SILVER_LISTENS GROUP BY LISTEN_KEY HAVING COUNT(*)>1 OR LISTEN_KEY IS NULL)
UNION ALL
SELECT 'unique_SILVER_ARTISTS',COUNT(*) FROM (SELECT ARTIST_MBID FROM VAYBA.DEV_HUGO_SILVER.SILVER_ARTISTS GROUP BY ARTIST_MBID HAVING COUNT(*)>1 OR ARTIST_MBID IS NULL);

SELECT * FROM VAYBA.DEV_HUGO_OPS.QUALITY_RESULTS ORDER BY CHECK_NAME;

SELECT * FROM VAYBA.DEV_HUGO_GOLD.METRICS_HEBDO;
