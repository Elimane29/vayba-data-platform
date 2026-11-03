with daily as (
 select
 {% if target.type == 'snowflake' %}
 regexp_substr(_source_file, 'artist=([^/]+)[.]json', 1, 1, 'e', 1) as artist_mbid,
 try_to_date(substr(item.value:timestamp::varchar, 1, 8), 'YYYYMMDD') as viewed_on,
 try_to_number(item.value:views::varchar) as pageviews,
 {% else %}
 nullif(regexp_extract(_source_file, 'artist=([^/]+)[.]json', 1), '') as artist_mbid,
 cast(try_strptime(substr(json_extract_string(item.value, '$.timestamp'), 1, 8), '%Y%m%d') as date) as viewed_on,
 try_cast(json_extract_string(item.value, '$.views') as bigint) as pageviews,
 {% endif %}
 _loaded_at, _batch_id, _source_file, cast(RAW as varchar) as raw_text
 from {{ source('bronze', 'WIKI_PAGEVIEWS_RAW') }},
 {% if target.type == 'snowflake' %}lateral flatten(input => RAW:items) item
 {% else %}lateral json_each(json_extract(RAW, '$.items')) item{% endif %}
), deduplicated as (
 select * from daily
 where artist_mbid is not null and viewed_on is not null and pageviews >= 0
 qualify row_number() over (
  partition by artist_mbid, viewed_on
  order by _loaded_at desc, _batch_id desc, _source_file desc, raw_text desc
 ) = 1
)
select artist_mbid, cast(date_trunc('week', viewed_on) as date) as week_start,
 sum(pageviews) as total_pageviews, count(*) as observed_days
from deduplicated group by artist_mbid, cast(date_trunc('week', viewed_on) as date)
