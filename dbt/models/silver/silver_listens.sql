select listen_key, user_key, {{ epoch_timestamp('listened_epoch') }} as listened_at,
 recording_msid, recording_mbid, track_name, artist_mbids, _source_file, _batch_id, _loaded_at
from {{ ref('listens_checked') }} where rejection_reason is null
