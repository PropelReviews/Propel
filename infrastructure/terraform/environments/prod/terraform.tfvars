# Prod environment (account 616938645090).
#
# App config is generic: CI forwards every GitHub Actions variable into
# `app_environment` (app.auto.tfvars.json). Sensitive values go in app_secrets.
# Local example:
#   app_environment = { POSTHOG_TOKEN = "phc_...", POSTHOG_HOST = "https://us.i.posthog.com" }

environment   = "prod"
zone_name     = "propel.ninja"
api_subdomain = "api"
app_subdomain = "app"

# Cross-account role assumed read-only to delegate beta.propel.ninja.
beta_zone_name    = "beta.propel.ninja"
beta_dns_role_arn = "arn:aws:iam::536270449640:role/PropelTerraform"

db_min_acu        = 0.5
db_max_acu        = 4
api_desired_count = 2
