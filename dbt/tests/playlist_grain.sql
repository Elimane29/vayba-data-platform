select week_start,user_key,position from {{ ref('playlist_hebdo') }} group by week_start,user_key,position having count(*)<>1
