STEP 2 — Production Database Foundation

Continue the Storage Lifecycle Optimizer project.

The repository foundation from Step 1 already exists.

For this step ONLY, design and implement the PostgreSQL database foundation.

IMPORTANT:
- Use PostgreSQL.
- PostgreSQL must run locally through the existing Docker Compose setup.
- Use only free/open-source technologies.
- Do NOT connect to a paid service.
- Do NOT implement the frontend UI.
- Do NOT implement cloud storage connectors.
- Do NOT implement lifecycle recommendations yet.
- Do NOT implement billing yet.
- Do NOT create a fake CSV dataset.
- Do NOT collect unnecessary personal information.

The database must be designed as a real multi-tenant SaaS database.

CORE REQUIREMENTS
 
1. Multi-tenancy

Organizations must be isolated from one another.

Create an organizations table.

Every organization-owned resource must be associated with organization_id.

Do not store unnecessary personal information.

Do not create employee names, phone numbers, addresses, personal emails, etc.

Use internal IDs and roles where necessary.

2. Users and roles

Create the minimum structure needed for organization membership and RBAC.

Support roles such as:

OWNER
ADMIN
OPERATOR
VIEWER

Do not implement the complete authentication system yet.

The database should be ready for authentication to be added later.

3. Subscriptions

Create a subscription structure that can support future SaaS plans.

Do not implement payment processing.

Store information such as:
- organization_id
- plan
- status
- limits
- created_at
- updated_at

Keep this extensible.

4. Storage connections

Create a storage_connections table representing an organization's connection to an external storage provider.

It should support providers such as:

AWS_S3
AZURE_BLOB
GOOGLE_CLOUD_STORAGE
LOCAL_S3_COMPATIBLE

Do NOT store raw cloud credentials in the database.

Use a credential_reference or secret_reference field instead.

5. Environments

Create development environments associated with an organization and storage connection.

Examples:
- development
- testing
- staging
- temporary CI environment

Store lifecycle-related metadata such as:
- environment status
- created_at
- last_activity_at
- expires_at

6. Storage locations

Create a storage_locations abstraction representing:
- bucket
- container
- namespace

It should belong to an organization and storage connection.

7. Objects

Create the main storage_objects table.

It must support metadata such as:

- object_id
- organization_id
- storage_location_id
- environment_id
- object_key
- object_size_bytes
- object_type
- storage_class
- created_at
- last_modified_at
- last_accessed_at
- access_count_30d
- access_count_90d
- version_count
- current_state
- discovered_at
- updated_at

IMPORTANT:

Do NOT store object contents.

Do NOT store file contents.

Do NOT store unnecessary personal data.

8. Access events

Create an access_events table for operational telemetry.

Store:
- object_id
- organization_id
- event_type
- event_timestamp
- source
- metadata necessary for analysis

Do not store unnecessary user-identifying information.

9. Restore events

Create restore_events.

Store:
- object_id
- organization_id
- requested_at
- completed_at
- status
- source_storage_class
- target_storage_class
- restore_duration
- failure_reason where applicable

10. Retention policies

Create retention_policies.

Support:
- organization-level policies
- environment-level policies
- storage-location-level policies
- object-level overrides where necessary

Store:
- retention duration
- effective date
- policy status
- priority
- created_at
- updated_at

11. Legal holds

Create legal_holds.

It must be possible to place a legal hold on an object.

Store:
- object_id
- organization_id
- status
- reason/reference
- created_at
- released_at

Do not store sensitive legal documents.

Only store the minimum metadata necessary.

12. Recommendations

Create recommendations.

A recommendation must preserve explainability.

Store:
- object_id
- organization_id
- recommendation_type
- current_storage_class
- recommended_storage_class
- reason
- evidence
- estimated_savings
- risk_level
- status
- created_at
- expires_at

The evidence should be structured JSON/JSONB where appropriate.

13. Approvals

Create approval_requests.

Support high-impact actions such as:

DELETE
MIGRATE
ARCHIVE

Store:
- recommendation_id
- organization_id
- requested_action
- status
- requested_at
- decided_at
- decision
- override_reason

Do not store unnecessary personal information.

14. Migration events

Create migration_events.

Track:

- object
- source storage class
- destination storage class
- requested time
- started time
- completed time
- status
- error
- rollback status

15. Rollbacks

Create rollback_events.

Track:
- migration_id
- reason
- requested_at
- completed_at
- status
- error

16. Audit logs

Create an audit_logs table.

Every important system action should eventually be auditable.

Support:
- organization_id
- action
- resource_type
- resource_id
- timestamp
- outcome
- metadata

Do not log secrets.

Do not log file contents.

Do not unnecessarily log personal information.

17. Cost snapshots

Create storage_cost_snapshots.

This will eventually allow the product to demonstrate:

BASELINE COST
vs
OPTIMIZED COST

Store:
- organization_id
- storage_location_id
- storage_class
- storage_bytes
- estimated_cost
- snapshot_date

18. Indexing

Design indexes for realistic queries.

Especially optimize for:

- organization_id
- environment_id
- storage_location_id
- object_id
- last_accessed_at
- storage_class
- current_state
- legal_hold status
- retention policy lookup
- recommendation status
- audit log queries

Avoid creating unnecessary indexes.

19. Tenant isolation

Document how tenant isolation will work.

At minimum:
- every tenant-owned table contains organization_id where appropriate
- foreign keys enforce relationships
- queries must always be scoped by organization
- prepare the schema so PostgreSQL Row Level Security can be introduced

Do NOT pretend that application-level filtering alone is sufficient for enterprise isolation.

20. Database migrations

Use a proper migration system.

Choose an appropriate free/open-source migration tool compatible with the selected backend stack.

Do NOT manually maintain a single giant SQL file as the only migration mechanism.

21. Seed data

Create ONLY minimal development seed data.

Use clearly fictional organizations such as:

Demo Organization
Test Organization

Do not generate thousands of fake objects yet.

We will create a controlled validation dataset later.

22. Database documentation

Update docs/architecture.md with:

- entity relationships
- tenant isolation approach
- important constraints
- indexing strategy
- retention/legal-hold precedence
- audit strategy
- data minimization strategy

Also create a database documentation file explaining the major tables.

23. Validation

After implementation:

- start PostgreSQL using Docker Compose
- run migrations
- run database tests
- verify foreign-key constraints
- verify unique constraints
- verify tenant relationships
- verify seed data
- verify the backend can connect to PostgreSQL

Do not continue to lifecycle logic after this.

At the end, report:

1. Database technology
2. Migration technology
3. Complete table list
4. Important relationships
5. Important indexes
6. Tenant isolation strategy
7. Privacy/data-minimization strategy
8. Tests performed
9. Any errors

STOP after completing STEP 2.