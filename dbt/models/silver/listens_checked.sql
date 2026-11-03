with parsed as (
 select
  coalesce(nullif({{ jtext('RAW', 'user_name') }}, ''),
   {% if target.type == 'snowflake' %}
   regexp_substr(_source_file, '(^|/)listenbrainz/week=[0-9]{4}-[0-9]{2}-[0-9]{2}/user=([^/]+)[.]json$', 1, 1, 'e', 2)
   {% else %}
   nullif(regexp_extract(_source_file, '(^|/)listenbrainz/week=[0-9]{4}-[0-9]{2}-[0-9]{2}/user=([^/]+)[.]json$', 2), '')
   {% endif %}
  ) as user_name,
  try_cast({{ jtext('RAW', 'listened_at') }} as bigint) as listened_epoch,
  {{ jtext('RAW', 'recording_msid') }} as recording_msid,
  {{ jtext('RAW', 'track_metadata.mbid_mapping.recording_mbid') }} as recording_mbid,
  {{ jtext('RAW', 'track_metadata.track_name') }} as track_name,
  {{ jarray('RAW', 'track_metadata.mbid_mapping.artist_mbids') }} as artist_mbids,
  {{ digest('_source_file') }} as _source_file, _batch_id, _loaded_at
 from {{ source('bronze', 'LISTENS_RAW') }}
), checked as (
 select *,
  {{ digest("coalesce(user_name, '')") }} as user_key,
  {{ digest("coalesce(user_name, '') || '|' || coalesce(cast(listened_epoch as varchar), '') || '|' || coalesce(recording_msid, '')") }} as listen_key,
  case when user_name is null then 'missing_user'
       when listened_epoch is null or listened_epoch < 0 or listened_epoch > 4102444800 then 'invalid_timestamp'
       when recording_msid is null then 'missing_recording_msid'
       when {% if target.type == 'snowflake' %}coalesce(array_size(artist_mbids), 0){% else %}coalesce(json_array_length(artist_mbids), 0){% endif %} = 0 then 'missing_artist_mbid'
       else null end as rejection_reason
 from parsed
)
select * exclude (user_name) from checked
qualify row_number() over (partition by listen_key order by _loaded_at desc, _batch_id desc, _source_file desc,
 coalesce(recording_mbid, ''), coalesce(track_name, ''), cast(artist_mbids as varchar)) = 1
