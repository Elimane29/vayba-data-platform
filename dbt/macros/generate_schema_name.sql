{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ target.schema }}{% if custom_schema_name %}_{{ custom_schema_name | trim | upper }}{% endif %}
{%- endmacro %}
