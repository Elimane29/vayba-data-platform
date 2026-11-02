select cast('{{ var("week_start", "2026-10-26") }}' as date) as week_start,
 count(*) as users_evaluated, avg(1.0 * hit) as hit_rate_s1, avg(1.0 * baseline_hit) as hit_rate_baseline_s1,
 (select avg(case when seen.artist_mbid is not null then 0.0 else 1.0 end) from {{ ref('playlist_hebdo') }} p left join {{ ref('user_artists') }} seen on seen.user_key=p.user_key and seen.artist_mbid=p.artist_mbid) as discovery_rate,
 (select max(_loaded_at) from {{ source('bronze', 'LISTENS_RAW') }}) as last_loaded_at
from {{ ref('evaluation_users') }}
