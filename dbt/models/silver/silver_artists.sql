select {{ jtext('RAW', 'id') }} as artist_mbid, {{ jtext('RAW', 'name') }} as artist_name,
 {{ jtext('RAW', 'country') }} as country, _loaded_at
from {{ source('bronze', 'MB_ARTISTS_RAW') }}
qualify row_number() over (partition by artist_mbid order by _loaded_at desc, _source_file desc, cast(RAW as varchar)) = 1
