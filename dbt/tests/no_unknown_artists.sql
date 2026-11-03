select l.artist_mbid from {{ ref('listen_artists') }} l left join {{ ref('silver_artists') }} a on l.artist_mbid=a.artist_mbid where a.artist_mbid is null
