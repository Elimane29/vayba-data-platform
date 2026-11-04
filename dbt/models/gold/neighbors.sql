with sizes as (
 select user_key, count(*) as n from {{ ref('user_artists') }} group by user_key
), common as (
 select a.user_key, b.user_key as neighbor_key,
 count(*) over (partition by a.user_key, b.user_key) as common_artists,
 a.artist_mbid as because_artist_mbid
 from {{ ref('user_artists') }} a join {{ ref('user_artists') }} b
 on a.artist_mbid = b.artist_mbid and a.user_key <> b.user_key
 qualify row_number() over (
  partition by a.user_key, b.user_key
  order by a.listens desc, b.listens desc, a.artist_mbid
 ) = 1
)
select c.*, 1.0 * common_artists / (a.n + b.n - common_artists) as similarity
from common c join sizes a on c.user_key = a.user_key join sizes b on c.neighbor_key = b.user_key
