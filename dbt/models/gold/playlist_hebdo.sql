with tracks as (
 select artist_mbid, recording_mbid, min(track_name) as track_name, count(*) as plays
 from {{ ref('train_listens') }} where recording_mbid is not null and track_name is not null
 group by artist_mbid, recording_mbid
), representative as (
 select * from tracks qualify row_number() over(partition by artist_mbid order by plays desc, recording_mbid) = 1
)
select cast('{{ var("week_start", "2026-10-26") }}' as date) as week_start, r.user_key,
 cast(r.recommendation_rank as integer) as position, t.recording_mbid, t.track_name,
 r.artist_mbid, a.artist_name,
 case when r.score is null then 'Popularité (secours)' else b.artist_name end as because_artist_name,
 coalesce(r.score, 0.0) as score
from {{ ref('ranked_artists') }} r join representative t on r.artist_mbid=t.artist_mbid
join {{ ref('silver_artists') }} a on r.artist_mbid=a.artist_mbid
left join {{ ref('silver_artists') }} b on r.because_artist_mbid=b.artist_mbid
where r.recommendation_rank <= {{ var('playlist_size', 10) }}
