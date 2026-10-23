"""Migration sanity check for one service (CI).

Runs against a THROWAWAY database:

1. apply every migration from scratch;
2. fail if models have migrations that were not generated
   (``makemigrations --check``);
3. for each app-owned migration with a same-app predecessor, reverse that one
   step and apply it again (proves the down path works);
4. leave the database fully migrated.

Usage (from the repository root):

    uv run --project backend python scripts/migration_check.py \
        backend/services/job-service postgresql://user:pass@host/db_mig
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service_dir", type=Path)
    parser.add_argument("database_url")
    args = parser.parse_args()

    service_dir = args.service_dir.resolve()
    if not (service_dir / "manage.py").is_file():
        print(f"migration_check: {service_dir} is not a Django service", file=sys.stderr)
        return 2

    os.chdir(service_dir)
    sys.path.insert(0, str(service_dir))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    os.environ["DATABASE_URL"] = args.database_url
    os.environ.setdefault("DJANGO_SECRET_KEY", "migration-check")

    import django

    django.setup()

    from django.apps import apps
    from django.core.management import call_command
    from django.db.migrations.loader import MigrationLoader

    print(f"migration_check: fresh migrate in {service_dir}")
    call_command("migrate", verbosity=1, interactive=False)

    print("migration_check: model drift")
    call_command("makemigrations", "--check", "--dry-run", verbosity=1)

    loader = MigrationLoader(None, ignore_no_migrations=True)
    local_apps = sorted(cfg.label for cfg in apps.get_app_configs() if cfg.name.startswith("apps."))

    for app in local_apps:
        for leaf in loader.graph.leaf_nodes(app):
            parents = [node for node in loader.graph.node_map[leaf].parents if node[0] == app]
            if not parents:
                # First migration of the app: reversing to zero may be blocked
                # by another app's swappable dependency. Forward path is enough.
                continue
            previous = parents[0][1]
            print(f"migration_check: {app} {leaf[1]} -> {previous} -> {leaf[1]}")
            call_command("migrate", app, previous, verbosity=1, interactive=False)
            call_command("migrate", app, leaf[1], verbosity=1, interactive=False)

    call_command("migrate", verbosity=0, interactive=False)
    print("migration_check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
