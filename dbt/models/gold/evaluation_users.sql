with future as (
 select distinct user_key, artist_mbid from {{ ref('listen_artists') }}
 where listened_at >= cast('{{ var("week_start", "2026-10-26") }}' as timestamp)
 and listened_at < cast('{{ var("test_end", "2026-11-02") }}' as timestamp)
), eligible as (
 select distinct u.user_key from {{ ref('user_artists') }} u join future f on u.user_key=f.user_key
), recommendations as (
 select user_key, artist_mbid from {{ ref('playlist_hebdo') }}
), baseline as (
 select user_key, artist_mbid from {{ ref('ranked_artists') }} where baseline_rank <= {{ var('playlist_size', 10) }}
), hits as (
 select distinct r.user_key from recommendations r join future f on r.user_key=f.user_key and r.artist_mbid=f.artist_mbid
), baseline_hits as (
 select distinct b.user_key from baseline b join future f on b.user_key=f.user_key and b.artist_mbid=f.artist_mbid
)
select e.user_key,
 case when h.user_key is not null then 1 else 0 end as hit,
 case when b.user_key is not null then 1 else 0 end as baseline_hit
from eligible e left join hits h on e.user_key=h.user_key
left join baseline_hits b on e.user_key=b.user_key
