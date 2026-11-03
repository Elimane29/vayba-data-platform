select 1 as incomplete
where (select count(*) from {{ ref('silver_listens') }} where listened_at >= cast('{{ var("history_start", "2026-09-21") }}' as timestamp) and listened_at < cast('{{ var("week_start", "2026-10-26") }}' as timestamp)) = 0
or (select max(listened_at) from {{ ref('silver_listens') }}) < cast('{{ var("test_end", "2026-11-02") }}' as timestamp) - interval '1 day'
