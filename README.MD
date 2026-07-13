# Propel

[![CI](https://github.com/PropelReviews/Propel/actions/workflows/ci.yml/badge.svg)](https://github.com/PropelReviews/Propel/actions/workflows/ci.yml)
[![Deploy Prod](https://github.com/PropelReviews/Propel/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/PropelReviews/Propel/actions/workflows/deploy-prod.yml)

Transparent analytics for engineering teams. Fully open source and self-hostable.

Your work in GitHub and Linear, turned into metrics you can read, trace, and trust. Built first for the developers doing the work, open to everyone who depends on it.

## Analytics shouldn't feel like surveillance

Most engineering analytics are a black box:

- Numbers generated where you can't see
- Scored by logic you can't read
- Handed down to the people they describe
- So people distrust it, dispute it, or game it

Propel is the opposite, by design:

- Fully open source and self-hostable
- Every metric is readable SQL
- Trace any number to the raw event
- Disagree? Fix it and open a pull request

Open measurement isn't a feature. It's the only kind developers will actually trust.

## Built for developers first

The work you already do, turned into evidence you own:

- **Fairer reviews** — walk in with data you can inspect, not a manager's memory
- **A brag doc that fills itself** — real commits, reviews, and shipped work, collected as you go
- **Resume datapoints** — concrete signal about what you actually shipped
- **Metrics you can change** — every number about you is open SQL; read it, question it, fix it

## The same numbers, for leaders

Leaders work from the exact metrics developers see, not a separate hidden scorecard:

- See where teams are stuck and what's slowing delivery
- Unblock people instead of measuring them from a distance
- Trust the rollup, because every number under it is inspectable

The team view defaults to aggregate signal. Drilling into one person is opt-in, never the default.

## What Propel measures

Propel pulls from your toolchain and surfaces the metrics that matter:

- **Cycle time** — how long work takes from PR open to merge (DORA lead-time proxy)
- **Throughput** — how much your team ships over time (DORA deployment-frequency proxy)
- **Review latency** — time to first review and review flow
- **Change failure** — revert rate as a DORA change-fail-rate proxy
- **Tooling activity** — signal from the tools your team already uses

The exact set evolves with the project. What never changes is that every number is inspectable, from dashboard to raw event.

## How it works

```
Your tools (GitHub, Linear)
        │
        ▼
   Meltano          ← data extraction
        │
        ▼
   Postgres         ← storage
        │
        ▼
   dbt              ← transformations
        │
        ▼
   Propel           ← dashboards + API
```

| Layer | Tool |
|---|---|
| Auth & multi-tenancy | FastAPI — users, tenants, roles ([data model](docs/backend/data-model.md)) |
| Extraction | Meltano |
| Database | Postgres |
| Transformations | dbt |
| Backend | FastAPI (Python) |
| Frontend | React |

Meltano extracts, Postgres stores, dbt transforms, and Propel presents. The API includes a multi-tenant auth layer (users, organizations, role-based access) above the analytics pipeline. See [docs/backend/data-model.md](docs/backend/data-model.md) for entity relationships.

## Deployment

The same software, however you run it. Identical open source software whether you run it or we do — pick what fits your team.

### Propel Cloud

[Propel Cloud](https://propel.ninja) is our managed platform. Same metrics, same SQL, same transparency — without running anything yourself.

Best if you want Propel up quickly and don't want to operate the stack.

### Self-hosted

Run the open source core in your own infrastructure. Your data never leaves your environment — full control over where it lives and who can touch it.

```bash
git clone https://github.com/PropelReviews/Propel
cd Propel
cp .env.example .env
docker compose up
```

No account required. No API keys phoning home. No telemetry unless you opt in.

Best if you have compliance requirements, want to run on private infrastructure, or prefer to operate the stack yourself.

See the **[self-hosting guide](docs/self-hosting.md)** for the full setup: environment variables, GitHub App and Linear OAuth configuration, and a production checklist.

## Documentation

Full documentation lives in [`docs/`](docs/README.md), including the
[self-hosting guide](docs/self-hosting.md), AWS
[deployment bootstrap runbook](docs/deployment/bootstrap.md),
[CI/CD](docs/deployment/cicd.md), and [local AWS SSO](docs/deployment/aws-sso.md).

## Contributing

Propel welcomes contributions — code, metrics, documentation, and bug reports. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

This repository is [MIT licensed](LICENSE), with the exception of the `ee/` directory (if applicable). Premium features in `ee/` require a Propel license for production use. See [ee/LICENSE](ee/LICENSE) for details.

Need a version with no proprietary code? Use only the MIT-licensed portions of this repository — everything outside `ee/` is fully open source.
