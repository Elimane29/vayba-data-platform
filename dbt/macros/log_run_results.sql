-- Production evidence uses OPS; developer evidence stays inside the developer schema.
-- runtime = where dbt ran: local (your laptop), docker (Docker lab) or airflow (Airflow lab).
{% macro log_run_results(results) %}
  {% if execute and target.type == "snowflake" and results | length > 0 %}
    {% set ops_schema = generate_schema_name('OPS', none) | trim %}
    {% set table = target.database ~ '.' ~ ops_schema ~ '.DBT_RESULTS' %}
    {% set runtime = env_var('VAYBA_RUNTIME', 'local') %}
    {% if target.name != 'prod' %}
      {% do run_query('create schema if not exists ' ~ target.database ~ '.' ~ ops_schema) %}
    {% endif %}
    {% do run_query('create table if not exists ' ~ table ~ ' (
        invocation_id varchar, run_at timestamp_tz, command varchar, runtime varchar,
        node varchar, resource_type varchar, status varchar,
        failures number, execution_seconds number(10,2))') %}
    {% set rows = [] %}
    {% for r in results %}
      {% do rows.append("('" ~ invocation_id ~ "', current_timestamp(), '" ~ flags.WHICH ~ "', '" ~ runtime ~ "', '"
          ~ r.node.unique_id ~ "', '" ~ r.node.resource_type ~ "', '" ~ r.status ~ "', "
          ~ (r.failures if r.failures is not none else 'null') ~ ", " ~ (r.execution_time | round(2)) ~ ")") %}
    {% endfor %}
    {% do run_query('insert into ' ~ table ~ ' values ' ~ rows | join(', ')) %}
  {% endif %}
{% endmacro %}
