select distinct l.listen_key, l.user_key, l.listened_at, l.recording_mbid, l.track_name,
 {% if target.type == 'snowflake' %}nullif(a.value::varchar, ''){% else %}nullif(json_extract_string(a.value, '$'), ''){% endif %} as artist_mbid
from {{ ref('silver_listens') }} l,
{% if target.type == 'snowflake' %}lateral flatten(input => l.artist_mbids) a
{% else %}lateral json_each(l.artist_mbids) a{% endif %}
where artist_mbid is not null
