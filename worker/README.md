# Background Worker Service

This module houses the asynchronous background job worker responsible for processing storage metadata ingestion, running lifecycle recommendation heuristics, and auditing lifecycle operations.

## Architecture
- **Task Dispatch**: Operates via background queue listening to incoming metadata jobs.
- **Stateless Execution**: Worker instances read normalized metadata records and output recommendation logs without storing state locally.
