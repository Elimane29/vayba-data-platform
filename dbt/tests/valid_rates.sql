select * from {{ ref('metrics_hebdo') }} where users_evaluated=0 or hit_rate_s1 not between 0 and 1 or hit_rate_baseline_s1 not between 0 and 1 or discovery_rate<>1
