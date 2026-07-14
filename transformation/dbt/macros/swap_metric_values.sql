-- Atomic per-metric swap into analytics.fct_metric_values (M4).
--
-- Called by the metrics compile job after regenerating a metric model.
-- Readers under REPEATABLE READ / default READ COMMITTED never observe
-- mixed definition_version rows for a metric_id: the delete+insert commits
-- together.
--
-- Args (dbt vars or call args):
--   metric_id  text
--   source_relation  — ref() to the freshly built metric model
--   tenant_ids  optional uuid[] — when set, scopes the delete to those tenants
--               (per-org models). When null, deletes by metric_id only (shared).

{% macro swap_metric_values(metric_id, source_relation, tenant_ids=none) %}
  begin;
  {% if tenant_ids is not none %}
  delete from {{ ref('fct_metric_values') }}
   where metric_id = '{{ metric_id }}'
     and tenant_id = any(array[
       {% for t in tenant_ids %}
         '{{ t }}'::uuid{% if not loop.last %},{% endif %}
       {% endfor %}
     ]);
  {% else %}
  delete from {{ ref('fct_metric_values') }}
   where metric_id = '{{ metric_id }}';
  {% endif %}

  insert into {{ ref('fct_metric_values') }} (
    tenant_id, metric_id, definition_version, grain,
    bucket_start, bucket_end, is_complete,
    dim_repo, dim_team, value, numerator, denominator
  )
  select
    tenant_id, metric_id, definition_version, grain,
    bucket_start, bucket_end, is_complete,
    dim_repo, dim_team, value, numerator, denominator
  from {{ source_relation }};
  commit;
{% endmacro %}
