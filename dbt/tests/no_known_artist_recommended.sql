select p.* from {{ ref('playlist_hebdo') }} p join {{ ref('user_artists') }} u on p.user_key=u.user_key and p.artist_mbid=u.artist_mbid
