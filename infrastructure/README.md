# Local Infrastructure Configuration

This directory contains local infrastructure configurations for development and testing.

## Services Included
- **PostgreSQL**: Open-source relational database for tenant data, metadata records, policy definitions, and audit logs.
- **Redis**: Open-source in-memory data store for background job queues and caching.

## Usage
To spin up local infrastructure containers:

```bash
docker-compose -f infrastructure/docker-compose.yml up -d
```
