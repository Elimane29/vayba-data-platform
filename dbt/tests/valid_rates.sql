select * from {{ ref('metrics_hebdo') }}
where users_evaluated = 0
 or hit_rate_s1 is null or hit_rate_s1 not between 0 and 1
 or hit_rate_baseline_s1 is null or hit_rate_baseline_s1 not between 0 and 1
 or discovery_rate is null or discovery_rate not between 0 and 1
 or wiki_coverage_rate is null or wiki_coverage_rate not between 0 and 1
 or lesser_known_rate not between 0 and 1
 or (wiki_coverage_rate = 0 and lesser_known_rate is not null)
 or (wiki_coverage_rate > 0 and lesser_known_rate is null)
 or lesser_known_pageviews_threshold <= 0
