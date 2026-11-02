with popularity as (
 select artist_mbid, count(distinct user_key) as users, count(*) as plays
 from {{ ref('train_listens') }} group by artist_mbid
), contributions as (
 select n.user_key, a.artist_mbid, n.similarity, n.because_artist_mbid,
 row_number() over (partition by n.user_key, a.artist_mbid order by n.similarity desc, n.neighbor_key) as rn
 from {{ ref('neighbors') }} n join {{ ref('user_artists') }} a on n.neighbor_key = a.user_key
 where not exists (select 1 from {{ ref('user_artists') }} seen where seen.user_key=n.user_key and seen.artist_mbid=a.artist_mbid)
), scores as (
 select user_key, artist_mbid, sum(similarity) as score,
 max(case when rn=1 then because_artist_mbid end) as because_artist_mbid
 from contributions group by user_key, artist_mbid
), pool as (
 select u.user_key, p.artist_mbid, p.users, p.plays, s.score, s.because_artist_mbid
 from (select distinct user_key from {{ ref('user_artists') }}) u cross join popularity p
 left join scores s on s.user_key=u.user_key and s.artist_mbid=p.artist_mbid
 where not exists (select 1 from {{ ref('user_artists') }} seen where seen.user_key=u.user_key and seen.artist_mbid=p.artist_mbid)
)
select *, row_number() over(partition by user_key order by case when score is null then 1 else 0 end, score desc, users desc, plays desc, artist_mbid) as recommendation_rank,
 row_number() over(partition by user_key order by users desc, plays desc, artist_mbid) as baseline_rank
from pool
