# Troubleshooting

## Startup migrations did not run

- `database.migrations_path` must point at the Alembic script directory —
  the one containing `env.py`, not the project root.
- Alembic is an optional dependency: `pip install pico-sqlalchemy[migrations]`.
  When the path is set without it, startup fails loudly with the install hint.
- `AlembicMigrator` runs at priority -100, before other `DatabaseConfigurer`
  hooks — if a seed hook needs migrated tables, keep its priority above -100.

## Alembic fails with an async driver error

The configured `database.url` (e.g. `postgresql+asyncpg://...`) is handed to
Alembic verbatim as `sqlalchemy.url`. Write `env.py` for the async URL —
Alembic's async template, or the `env.py` from the
[Alembic how-to](how-to/alembic.md) — or derive a sync engine inside your
`env.py`.

## `MissingGreenlet` or "greenlet_spawn has not been called"

An async session was used from sync code. Access the session inside
`@transactional` async methods, or use `run_sync` for sync-only helpers.

## My `@query` method returns nothing / the wrong type

Derived queries parse the method NAME; check the prefix (`find_by_`,
`count_by_`, `exists_by_`) and that parameter names match column names.
Explicit `@query("...")` strings bypass name parsing entirely.

## Changes are not persisted

Writes must happen inside a transaction boundary: `@transactional` on the
method (or an enclosing one — REQUIRED propagation reuses it). Reads outside
a transaction run in autocommit and see committed state only.

## `pool_size` seems ignored

With SQLite `:memory:` URLs, pool settings are not applied (single
connection semantics). They take effect on real server databases.
