"""Service layer for Clay integrations, reporting, and monitoring.

This package exposes cohesive building blocks so that Flask routes, CLIs, and
background workers can orchestrate data flows without knowing implementation
details.  Think of it as a façade over three concerns:

- Clay ingestion (`ClaySyncService`): Fetches data, normalizes it into the
  Supabase schema, and keeps bridge tables in sync.
- Reporting (`ReportingService`): Aggregates company intelligence for weekly
  digests and email delivery.
- Watchdog (`WatchdogService`): Compares stored data with fresh Clay snapshots to
  detect drift and later trigger notifications.

Importing from `services` keeps call sites clean, e.g.:

```
from services import ClaySyncService
```
"""

from .clay import ClayClient
from .ingestion import ClaySyncService
from .reporting import ReportingService
from .watchdog import WatchdogService

__all__ = [
    "ClayClient",
    "ClaySyncService",
    "ReportingService",
    "WatchdogService",
]

