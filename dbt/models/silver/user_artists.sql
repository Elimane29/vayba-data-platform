select user_key, artist_mbid, count(*) as listens
from {{ ref('train_listens') }} group by user_key, artist_mbid
