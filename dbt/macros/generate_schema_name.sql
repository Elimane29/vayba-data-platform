-- Use the schema names exactly as written (SILVER, GOLD) instead of dbt's default
-- "<target schema>_<custom schema>" naming.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim | upper }}{%- endif -%}
{%- endmacro %}
