with evaluated_listens as (
 select l.listen_key,
  max(case when seen.artist_mbid is not null then 1 else 0 end) as known_artist
 from {{ ref('listen_artists') }} l
 join {{ ref('evaluation_users') }} e on e.user_key = l.user_key
 left join {{ ref('user_artists') }} seen
  on seen.user_key = l.user_key and seen.artist_mbid = l.artist_mbid
 where l.listened_at >= cast('{{ var("week_start", "2026-10-26") }}' as timestamp)
  and l.listened_at < cast('{{ var("test_end", "2026-11-02") }}' as timestamp)
 group by l.listen_key
), recommended_artists as (
 select distinct week_start, artist_mbid from {{ ref('playlist_hebdo') }}
), notoriety as (
 select
  avg(case when w.observed_days = 7 then
    case when w.total_pageviews < {{ var('lesser_known_pageviews_threshold', 1000) }} then 1.0 else 0.0 end
  end) as lesser_known_rate,
  avg(case when w.observed_days = 7 then 1.0 else 0.0 end) as wiki_coverage_rate
 from recommended_artists p left join {{ ref('silver_wiki_pageviews') }} w
  on p.artist_mbid = w.artist_mbid and p.week_start = w.week_start
)
select cast('{{ var("week_start", "2026-10-26") }}' as date) as week_start,
 count(*) as users_evaluated, avg(1.0 * hit) as hit_rate_s1,
 avg(1.0 * baseline_hit) as hit_rate_baseline_s1,
 (select avg(1.0 - known_artist) from evaluated_listens) as discovery_rate,
 (select max(_loaded_at) from {{ source('bronze', 'LISTENS_RAW') }}) as last_loaded_at,
 (select lesser_known_rate from notoriety) as lesser_known_rate,
 (select wiki_coverage_rate from notoriety) as wiki_coverage_rate,
 {{ var('lesser_known_pageviews_threshold', 1000) }} as lesser_known_pageviews_threshold
from {{ ref('evaluation_users') }}
