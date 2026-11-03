{% macro generate_schema_name(custom_schema_name, node) -%}
  {% if target.name == 'prod' %}
    {{ custom_schema_name | trim | upper if custom_schema_name else target.schema }}
  {% else %}
    {{ target.schema }}{% if custom_schema_name %}_{{ custom_schema_name | trim | upper }}{% endif %}
  {% endif %}
{%- endmacro %}
