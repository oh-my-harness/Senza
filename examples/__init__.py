"""Discover and run Senza's executable learning scenarios.

The package is an additive catalog/runner overlay.  The canonical scenario
implementations remain in ``live-tests/examples`` during the migration.
"""

from .catalog import Catalog, CatalogError, Scenario, load_catalog

__all__ = ["Catalog", "CatalogError", "Scenario", "load_catalog"]

