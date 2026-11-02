{% macro jtext(expr, path) -%}
{% if target.type == 'snowflake' %}nullif({{ expr }}:{{ path | replace('.', ':') }}::varchar, '')
{% else %}nullif(json_extract_string({{ expr }}, '$.{{ path }}'), ''){% endif %}
{%- endmacro %}
{% macro jarray(expr, path) -%}
{% if target.type == 'snowflake' %}{{ expr }}:{{ path | replace('.', ':') }}
{% else %}json_extract({{ expr }}, '$.{{ path }}'){% endif %}
{%- endmacro %}
{% macro digest(expr) -%}
{% if target.type == 'snowflake' %}sha2({{ expr }}, 256){% else %}sha256({{ expr }}){% endif %}
{%- endmacro %}
{% macro epoch_timestamp(expr) -%}
{% if target.type == 'snowflake' %}to_timestamp_ntz({{ expr }}){% else %}timezone('UTC', to_timestamp({{ expr }})){% endif %}
{%- endmacro %}
