"""Ingestion orchestration (landing only).

A thin coordinator: it iterates active connected_accounts, mints GitHub App
installation tokens, invokes Meltano jobs (which land data via target-propel),
and owns the ingestion_run lifecycle. It does not reimplement tap logic and does
not transform anything.
"""
