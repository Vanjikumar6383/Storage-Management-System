We are building a production-oriented multi-tenant SaaS platform called
"Storage Lifecycle Optimizer".

IMPORTANT DEVELOPMENT CONSTRAINT:

The entire project must use FREE and/or OPEN-SOURCE resources during development,
testing, and the initial demonstration.

Do NOT introduce:
- paid APIs
- paid AI APIs
- paid datasets
- paid SaaS services
- paid cloud infrastructure
- paid database services
- commercial software licenses

Prefer:
- open-source software
- local development
- free tiers
- PostgreSQL
- Python
- TypeScript
- React/Next.js
- FastAPI
- Docker
- Git
- GitHub
- free deployment tiers where appropriate

Do not add a dependency merely because it is convenient.
Evaluate its license and whether it is appropriate for a future commercial SaaS
before introducing it.

PROJECT PURPOSE:

The platform helps organizations reduce cloud-storage costs by analyzing
storage-object metadata and recommending lifecycle actions.

The system will analyze:
- object age
- object size
- access frequency
- last access time
- storage class
- retention policies
- legal holds
- restore events
- environment lifecycle
- estimated storage cost

Possible recommendations:
- KEEP
- MOVE_TO_INFREQUENT_ACCESS
- ARCHIVE
- DELETE_CANDIDATE
- HOLD

PRODUCT REQUIREMENTS:

1. Production-oriented SaaS architecture.
2. Multi-tenant organization isolation.
3. Metadata-first architecture.
4. Do not collect unnecessary personal data.
5. Do not collect file contents unless absolutely necessary.
6. Retention rules must override deletion decisions.
7. Legal holds must prevent deletion.
8. High-impact actions require human confirmation.
9. Every recommendation must contain explainable evidence.
10. Users can override recommendations.
11. Override reasons must be recorded.
12. Lifecycle migrations must be auditable.
13. Lifecycle migrations must support rollback.
14. Background jobs must be supported.
15. Cloud storage connectors must eventually be supported.
16. A legacy workflow must be supported during migration/coexistence.
17. The system must measure cost before and after optimization.
18. The system must detect and report errors/failures.
19. The architecture must be extensible for future subscription/billing features.
20. Never hard-code secrets or credentials.

FOR THIS TASK ONLY:

Create the initial repository foundation.

Do NOT implement:
- lifecycle rules
- recommendation engine
- cloud connectors
- authentication
- database schema
- billing
- dashboard
- fake datasets
- AI/ML
- migration execution

First inspect the repository.

Then propose a minimal production-oriented stack using only free/open-source
technologies.

Explain:
1. Selected frontend technology.
2. Selected backend technology.
3. Database choice.
4. Background-job approach.
5. Testing approach.
6. Local development approach.
7. Why every selected technology can be used without paying during development.
8. Any licensing considerations.

Then create ONLY the initial foundation.

Create appropriate directories for:

frontend
backend
worker
shared
infrastructure
docs
tests

Also create:

README.md
.env.example
.gitignore

Create architecture documentation describing:
- system boundaries
- frontend/backend separation
- future storage connectors
- metadata ingestion
- lifecycle engine
- approval workflow
- audit system
- rollback system
- tenant isolation

IMPORTANT:

Do not add unnecessary dependencies.

Do not use paid services.

Do not use a paid AI API.

Do not generate fake business data.

Do not create placeholder code pretending that features already work.

After creating the foundation:

1. Show the directory tree.
2. Show installed dependencies.
3. Verify the project builds.
4. Verify the development server starts.
5. Run the available tests.
6. Report errors honestly.
7. Explain what was actually implemented.

STOP after completing this task.
Do not continue implementing future features.