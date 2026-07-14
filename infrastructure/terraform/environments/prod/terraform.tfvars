# Prod environment (account 616938645090).
#
# App config is generic: CI forwards every GitHub Actions variable into
# `app_environment` (app.auto.tfvars.json). Sensitive values go in app_secrets.
# Local example:
#   app_environment = { POSTHOG_TOKEN = "phc_...", POSTHOG_HOST = "https://us.i.posthog.com" }

environment       = "prod"
zone_name         = "propel.ninja"
api_subdomain     = "api"
app_subdomain     = "app"
dagster_subdomain = "dagster"

# Aurora Serverless v2: min stays at 0.5 ACU. Scale-to-zero (min=0) is blocked
# while PostHog CDC logical replication is enabled. Cap max at 2 ACU to match
# the previous beta sizing and limit peak RDS spend.
db_min_acu        = 0.5
db_max_acu        = 2
db_engine_version = "18.3"
# Single API task is enough at current traffic; ECS still does a rolling replace
# (default maxPercent=200) so deploys stay zero-downtime.
api_desired_count = 1
