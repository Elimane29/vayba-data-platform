select artist_mbid, week_start from {{ ref('silver_wiki_pageviews') }}
group by artist_mbid, week_start
having count(*) <> 1 or artist_mbid is null or week_start is null
 or min(total_pageviews) < 0 or min(observed_days) < 1 or max(observed_days) > 7
