select * from {{ ref('listen_artists') }}
where listened_at >= cast('{{ var("history_start", "2026-09-21") }}' as timestamp)
 and listened_at < cast('{{ var("week_start", "2026-10-26") }}' as timestamp)
