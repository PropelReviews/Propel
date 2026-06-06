# Propel

Open source developer analytics for teams that want to trust their metrics.

Propel connects to your existing tools (GitHub, Linear, Cursor) and turns raw engineering activity into performance metrics your team can inspect, question, and own.

## Why Propel

Most developer analytics tools optimize for managers. Propel optimizes for engineers.

Performance measurement only works when the people being measured trust it. That requires transparency at every layer: the source data, the transformation logic, and the final numbers on the dashboard. When any of that is hidden, metrics feel like surveillance. When all of it is visible, they become a shared basis for accountability.

Propel is built on that principle. Every metric is defined in open, readable SQL. Every step in the pipeline is open source. If you want to know how a number was calculated, you can trace it from dashboard to query to raw event.

## What Propel measures

Propel pulls data from your toolchain and surfaces engineering metrics such as:

- **Cycle time** — how long work takes from start to finish
- **Throughput** — how much work your team ships over time
- **Review patterns** — how code review flows through your process
- **Tooling activity** — signals from the tools your team already uses

The exact metrics evolve with the project. What stays constant is that every one of them is inspectable.

## Architecture

```
Your tools (GitHub, Linear, Cursor)
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
| Extraction | Meltano |
| Database | Postgres |
| Transformations | dbt |
| Backend | FastAPI (Python) |
| Frontend | React |

Meltano extracts, Postgres stores, dbt transforms, and Propel presents. Each layer is either in this repository or a well-known open source project you can audit on your own.

## Deployment

Propel is the same open source software whether you run it yourself or we run it for you. Pick the option that fits your team.

### Propel Cloud

[Propel Cloud](https://propel.ninja) is the managed version of Propel. We handle infrastructure, updates, and operations — you get the same metrics, the same SQL, and the same transparency without running anything yourself.

Best if you want Propel running quickly and don't want to operate the stack.

### Self-hosted

Run Propel entirely in your own infrastructure. Your data never leaves your environment — full control over where it lives, who can access it, and how it connects to your internal tools.

```bash
git clone https://github.com/PropelReviews/Propel
cd Propel
cp .env.example .env
docker-compose up
```

No account required. No API keys phoning home. No telemetry unless you opt in.

Best if you have compliance requirements, want to run on private infrastructure, or prefer to operate the stack yourself.

## Contributing

Propel welcomes contributions — code, metrics, documentation, and bug reports. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

This repository is [MIT licensed](LICENSE), with the exception of the `ee/` directory (if applicable). Premium features in `ee/` require a Propel license for production use. See [ee/LICENSE](ee/LICENSE) for details.

Need a version with no proprietary code? Use only the MIT-licensed portions of this repository — everything outside `ee/` is fully open source.
