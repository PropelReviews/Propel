# Beta environment (account 536270449640).
#
# App config is generic: CI forwards every GitHub Actions variable into
# `app_environment` (written to app.auto.tfvars.json at deploy time), so adding
# a key in the GitHub org/repo Actions variables is enough -- no code changes.
# For local runs you can set it inline, e.g.:
#   app_environment = { POSTHOG_TOKEN = "phc_...", POSTHOG_HOST = "https://metrics.propelreview.com" }
# Sensitive values go in app_secrets (stored in Secrets Manager) instead.

environment       = "beta"
zone_name         = "beta.propel.ninja"
api_subdomain     = "api"
app_subdomain     = "app"
dagster_subdomain = "dagster"

db_min_acu        = 0
db_max_acu        = 2
api_desired_count = 1
