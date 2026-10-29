# Week 5 Write-up

**Repos chosen**, and how they differ:

| Repo | Language | Size | Age / activity |
|---|---|---|---|
| [blader/humanizer](https://github.com/blader/humanizer) | Python + Markdown (agent skill) | 14 files, 476 KB | Created 2026-01-18 (~9 months); 101 commits, one main author |
| [ucam-eo/geotessera](https://github.com/ucam-eo/geotessera) | Python | 71 files, 83 MB | Created 2025-07-02 (~16 months); 525 commits, small academic group |
| [supabase/supabase](https://github.com/supabase/supabase) | TypeScript / JavaScript | 18,255 files, 1.4 GB | Created 2019-10-12 (~7 years); corporate-backed, 11 applications |

## Part I: Report Results

### Summary

| Repo | Maturity level | Blocking the next level | Pillar scores |
|---|---|---|---|
| humanizer | Level 2 — Documented | The report said some things about blocking, but imo, I disagree, and think that this repo (purely a skill with 1 python file) does not need a linter, devcontainer, etc.  | Style 9.1%; Build 46.2%; Testing 20.0%; Docs 71.4%; Dev Env 0.0%; Observability 0.0%; Security 7.7% |
| geotessera | Level 2 — Documented | Level 2 items missing (AGENTS.md, pre-commit hooks, devcontainer, branch protection unverified); tests not runnable for an agent | Style 15.4%; Build 22.2%; Testing 40.0%; Docs 58.3%; Dev Env 80.0%; Observability 10.0%; Security 16.7% |
| supabase | Level 3 — Standardized | Level 3 items (pre-commit hooks, coverage thresholds, secret scanning unverified, tracing and metrics across apps); Level 4 (PR CI 14.8 min, deployment frequency, flaky-test detection) | Style 30.3%; Build 63.2%; Testing 38.2%; Docs 84.1%; Dev Env 50.9%; Observability 16.1%; Security 68.2% |

### Failed criteria by pillar

| Pillar | humanizer | geotessera | supabase |
|---|---|---|---|
| Style & Validation | linter; type checker; formatter; pre-commit hooks; strict typing; naming consistency; cyclomatic complexity; dead-code detection; duplicate-code detection; tech-debt tracking | large-file detection; tech-debt tracking; automated PR review; type check; pre-commit hooks; strict typing; naming consistency; cyclomatic complexity; dead-code detection; duplicate-code detection; code modularization | large-file detection; tech-debt tracking; lint config (6/11); type check (10/11); formatter (8/11); pre-commit hooks (0/11); strict typing (7/11); naming consistency (1/11); cyclomatic complexity (0/11); dead-code detection (8/11); duplicate-code detection (0/11); code modularization (0/11) |
| Build System | dependencies pinned; build-performance tracking; deployment frequency; feature flags; release-notes automation; unused-dependency detection; release automation | fast CI feedback; build-performance tracking; deployment frequency; feature flags; release-notes automation; unused-dependency detection; release automation | fast CI feedback; deployment frequency; release-notes automation; rollback automation; heavy-dependency detection (3/11); unused-dependency detection (8/11); version-drift detection; dead-feature-flag detection |
| Testing | unit tests exist; integration tests exist; unit tests runnable; test-performance tracking; flaky-test detection; coverage thresholds; test naming; test isolation | unit tests runnable; test-performance tracking; flaky-test detection; coverage thresholds; test naming; test isolation | unit tests exist (5/11); integration tests exist (5/11); unit tests runnable (0/11); test-performance tracking (4/11); flaky-test detection (4/11); coverage thresholds (0/11); test naming (2/11); test isolation (6/11); interactive QA exists (8/11); interactive QA runnable (8/11) |
| Documentation | automated doc generation; service-flow documentation | AGENTS.md; AGENTS.md validation; runbooks; issue labeling system; PR templates | API schema docs (8/11); AGENTS.md validation |
| Dev Environment | devcontainer; environment template | devcontainer | devcontainer; database schema (6/11); runbooks |
| Code Quality | was not present in the report| was not in the report| was not in the report |
| Observability | structured logging; distributed tracing; metrics collection; contextualized error tracking; alerting; runbooks; deployment observability | structured logging; distributed tracing; metrics collection; contextual error tracking; alerting; deployment observability; profiling; product analytics; error-to-insight pipeline | N+1 detection (0/11); structured logging (3/11); distributed tracing (2/11); metrics collection (4/11); code-quality metrics (1/11); error tracking (1/11); alerting (1/11); deployment observability (0/11); health checks (2/11); circuit breakers (4/11); profiling (0/11); product analytics (4/11); error-to-insight (1/11) |
| Security & Governance | CODEOWNERS; dependency-update automation; comprehensive gitignore; PII handling; secrets management; log scrubbing; minimum release age; issue labeling system; backlog health; PR templates; product analytics; error-to-insight pipeline | CODEOWNERS; dependency-update automation; comprehensive gitignore; minimum release age; log scrubbing | comprehensive gitignore; DAST scanning (1/11); PII handling (4/11); log scrubbing (1/11); issue templates |

### The report's top remediation suggestions

| Repo | Suggestions |
|---|---|
| humanizer | 1. Add focused unit tests for the package validator, with a coverage gate in CI. 2. Configure Python linting, formatting, and type checks, then run them through pre-commit hooks. 3. Add a `.gitignore` and PR template, and define priority and area labels for issues. |
| geotessera | 1. Add a root `AGENTS.md` with verified setup and test commands, and add pre-commit Ruff checks. 2. Make the documented development setup reliably collect tests, then enforce a coverage threshold. 3. Reduce PR feedback time by splitting or optimizing the multi-platform CI matrix. |
| supabase | 1. Add pre-commit lint and formatting hooks, plus a coverage threshold. 2. Reduce primary PR CI below 10 minutes through narrower jobs or improved caching. 3. Add an automated release-note workflow and a documented rollback action. |

### Raw output

```
########## blader/humanizer ##########
📊 Starting agent readiness evaluation for: https://github.com/blader/humanizer.git
# Level
Level 2. The repository passes 15 of 63 evaluated criteria (23.8%); 21 criteria were skipped.

# Applications
1. `.` - Portable Humanizer skill for rewriting AI-sounding prose.

# Criteria

**Style & Validation**
- Linter configured: 0/1 - No Python linter is configured.
- Type checker: 0/1 - No static type checker is configured.
- Formatter: 0/1 - No automated formatter is configured.
- Pre-commit hooks: 0/1 - No checked-in hooks exist.
- Strict typing: 0/1 - No strict type-checking mode is configured.
- Naming consistency: 0/1 - No Python naming rule or naming linter exists.
- Cyclomatic complexity: 0/1 - No complexity check is configured.
- Large file detection: 1/1 - CI rejects `SKILL.md` above 5,500 words.
- Dead code detection: 0/1 - No unused-code detector is configured.
- Duplicate code detection: 0/1 - No duplication detector is configured.
- Code modularization: null/1 - Skipped; this small skill has no meaningful module boundaries.
- Tech debt tracking: 0/1 - No debt-marker tracking is configured.
- N+1 detection: null/1 - Skipped; there is no database or ORM.

**Build System**
- Build command documented: 1/1 - `AGENTS.md` explains that there is no build step and lists validation commands.
- Dependencies pinned: 0/1 - No committed lockfile or pinned dependency set exists.
- VCS CLI tools: 1/1 - GitHub CLI is installed and authenticated.
- Automated PR review: 1/1 - Copilot generated a substantive review on PR #286.
- Agentic development: 1/1 - Commits include Claude co-author and session records.
- Fast CI feedback: 1/1 - Checks on 10 recent PRs finished in 9–33 seconds.
- Build performance tracking: 0/1 - No build timing or performance monitoring is configured.
- Deployment frequency: 0/1 - Releases are less frequent than multiple times a week; no deploy workflow exists.
- Single-command setup: 1/1 - README gives an install command and `/humanizer` invocation.
- Feature flag infrastructure: 0/1 - No feature flags are configured.
- Release notes automation: 0/1 - The changelog is maintained manually.
- Progressive rollout: null/1 - Skipped; the skill has no deployment infrastructure.
- Rollback automation: null/1 - Skipped; the skill has no deployment infrastructure.
- Monorepo tooling: null/1 - Skipped; this is one root package.
- Heavy dependency detection: null/1 - Skipped; the skill is not bundled.
- Unused dependencies detection: 0/1 - No dependency-use check is configured.
- Version drift detection: null/1 - Skipped; there are no sibling build modules.
- Release automation: 0/1 - CI validates the package but does not release it.
- Dead feature flag detection: null/1 - Skipped; there are no feature flags.

**Testing**
- Unit tests exist: 0/1 - No unit test files exist.
- Integration tests exist: 0/1 - No integration suite exists.
- Unit tests runnable: 0/1 - There is no unit test file to collect; package validation is not a unit test.
- Test performance tracking: 0/1 - CI does not retain or analyze test timings.
- Flaky test detection: 0/1 - No retry, quarantine, or stability tooling exists.
- Test coverage thresholds: 0/1 - No coverage gate exists.
- Test naming conventions: 0/1 - No test naming rule is configured.
- Test isolation: 0/1 - No test isolation setup exists.
- Interactive QA documented: 1/1 - README covers installation and a rewrite interaction.
- Interactive QA runnable: 1/1 - The documented path is complete and the package validator passed; an installed-agent interaction was not launched.

**Documentation**
- `AGENTS.md`: 1/1 - Root guidance covers layout, editing rules, and checks.
- README: 1/1 - Installation, use, and examples are documented.
- Automated doc generation: 0/1 - No documentation generator is configured.
- Skills: 1/1 - Root `SKILL.md` has valid metadata and instructions.
- Documentation freshness: 1/1 - README changed on 2026-10-16.
- API schema docs: null/1 - Skipped; there is no service API.
- Service flow documented: 0/1 - No architecture or dependency document exists.
- `AGENTS.md` validation: 1/1 - CI runs the checks listed in `AGENTS.md`.

**Dev Environment**
- Devcontainer: 0/1 - No devcontainer configuration exists.
- Environment template: 0/1 - No `.env.example` or environment-variable guidance exists.
- Local services setup: null/1 - Skipped; no local services are needed.
- Database schema: null/1 - Skipped; there is no database.
- Devcontainer runnable: null/1 - Skipped; the CLI is unavailable and no container is configured.

**Debugging & Observability**
- Structured logging: 0/1 - No structured logger exists.
- Distributed tracing: 0/1 - No trace propagation exists.
- Metrics collection: 0/1 - No telemetry is configured.
- Code quality metrics: null/1 - Skipped; no local metrics exist and native scanning cannot be verified without admin access.
- Contextualized error tracking: 0/1 - No error tracker is configured.
- Alerting: 0/1 - No alert rules exist.
- Runbooks: 0/1 - No incident runbook is documented.
- Deployment observability: 0/1 - No deployment dashboard or notification guidance exists.
- Health checks: null/1 - Skipped; this is not a deployed service.
- Circuit breakers: null/1 - Skipped; the package makes no external service calls.
- Profiling: null/1 - Skipped; runtime profiling is not meaningful for the static skill.

**Security**
- Branch protection: null/1 - Skipped; the authenticated account lacks repository admin access.
- Secret scanning: null/1 - Skipped; no local scanner exists and native scanning cannot be verified without admin access.
- CODEOWNERS: 0/1 - No CODEOWNERS file exists.
- Automated security review: null/1 - Skipped; no local workflow exists and native scanning cannot be verified without admin access.
- Dependency update automation: 0/1 - No Dependabot or equivalent is configured.
- Comprehensive gitignore: 0/1 - No `.gitignore` exists.
- DAST scanning: null/1 - Skipped; this is not a web service.
- PII handling: 0/1 - No PII detection or handling procedure is configured for user-supplied text.
- Privacy compliance: null/1 - Skipped; the repository does not collect end-user data.
- Secrets management: 0/1 - No secrets-management pattern is evident.
- Log scrubbing: 0/1 - No redaction mechanism or guidance exists.
- Minimum release age: 0/1 - No dependency waiting-period policy exists.
- Issue templates: 1/1 - Structured issue forms request examples and expected behavior.
- Issue labeling system: 0/1 - Labels lack priority and area categories.
- Backlog health: 0/1 - All three open issues have descriptive titles, but none has a label.
- PR templates: 0/1 - No pull request template exists.
- Product analytics: 0/1 - No usage instrumentation exists.
- Error-to-insight pipeline: 0/1 - No error-to-issue integration exists.

# Action Items
- Add focused unit tests for the package validator, with a coverage gate in CI.
- Configure Python linting, formatting, and type checks, then run them through pre-commit hooks.
- Add a `.gitignore` and PR template, and define priority and area labels for issues.

---
View the full report: https://app.factory.ai/analytics/readiness/https%253A%252F%252Fgithub.com%252Fblader%252Fhumanizer

########## ucam-eo/geotessera ##########
📊 Starting agent readiness evaluation for: https://github.com/ucam-eo/geotessera.git
# Level
**Level 2**: 21 of 65 evaluated criteria pass (32.3%). Nineteen criteria were skipped.

# Applications
1. `.` - GeoTessera Python library and CLI for accessing Tessera geospatial embeddings.

# Criteria
`null/1` means the criterion was skipped.

**Style & Validation**
- Large File Detection: 0/1 - No size threshold, hook, or LFS rule.
- Tech Debt Tracking: 0/1 - No debt-marker enforcement or tracking configuration.
- Automated PR Review: 0/1 - Recent PRs have no automated review content.
- Lint Config: 1/1 - Ruff is a development dependency.
- Type Check: 0/1 - No Python type checker configured.
- Formatter: 1/1 - Ruff formatting is documented.
- Pre-commit Hooks: 0/1 - No quality-check hooks configured.
- Strict Typing: 0/1 - No strict type-checking configuration.
- Naming Consistency: 0/1 - No enforced naming rules.
- Cyclomatic Complexity: 0/1 - No complexity threshold or analyzer.
- Dead Code Detection: 0/1 - No unused-code detector.
- Duplicate Code Detection: 0/1 - No duplication scanner.
- Code Modularization: 0/1 - No enforced module boundaries.
- N+1 Detection: null/1 - No database or ORM queries.

**Build System**
- Build Command Documented: 1/1 - README documents development installation.
- Dependencies Pinned: 1/1 - `uv.lock` is committed and CI uses `--locked`.
- Fast CI Feedback: 0/1 - Measured PR checks average 33.3 minutes.
- Build Performance Tracking: 0/1 - No deliberate build-duration monitoring.
- Deployment Frequency: 0/1 - No automated deployment workflow or multiple weekly releases.
- Feature Flag Infrastructure: 0/1 - No feature-toggle system.
- Release Notes Automation: 0/1 - Changelog exists, but generation is not automated.
- Progressive Rollout: null/1 - Not an infrastructure deployment repository.
- Rollback Automation: null/1 - No service deployment lifecycle.
- Monorepo Tooling: null/1 - One build package.
- Version Drift Detection: null/1 - No sibling build modules.
- Release Automation: 0/1 - CI tests but does not publish releases.
- Dead Feature Flag Detection: null/1 - No feature-flag infrastructure.
- Heavy Dependency Detection: null/1 - No bundled frontend.
- Unused Dependencies Detection: 0/1 - No unused-dependency check.

**Testing**
- Unit Tests Exist: 1/1 - Python and CLI tests are present.
- Integration Tests Exist: 1/1 - CLI tests exercise a local Zarr store and GeoTIFF output.
- Unit Tests Runnable: 0/1 - Bounded pytest collection failed because `geopandas` is missing; no tests ran.
- Test Performance Tracking: 0/1 - No retained timing reports or analytics.
- Flaky Test Detection: 0/1 - No retry, quarantine, or stability tooling.
- Test Coverage Thresholds: 0/1 - No minimum coverage gate.
- Test Naming Conventions: 0/1 - Naming is followed but not enforced.
- Test Isolation: 0/1 - No configured parallelism, randomization, or isolation policy.
- Interactive QA Exists: 1/1 - README documents install and CLI interactions.
- Interactive QA Runnable: 1/1 - The documented credential-free path qualifies for fallback; the local attempt stopped on missing `geopandas`.

**Documentation**
- AGENTS.md: 0/1 - No root `AGENTS.md`.
- README: 1/1 - Covers installation and usage.
- Automated Doc Generation: 1/1 - Sphinx autodoc and Read the Docs are configured.
- Skills: 1/1 - A valid GeoTessera agent skill exists.
- Documentation Freshness: 1/1 - README changed within 180 days.
- Service Flow Documented: 1/1 - Architecture guide describes layers and data flow.
- AGENTS.md Validation: 0/1 - No `AGENTS.md` to validate.
- Runbooks Documented: 0/1 - No incident-response runbook or pointer.
- Issue Templates: 1/1 - Two structured request templates exist.
- Issue Labeling System: 0/1 - No priority, type, and area taxonomy.
- Backlog Health: 1/1 - 44 of 50 sampled open issues have descriptive titles and labels.
- PR Templates: 0/1 - No pull request template.
- API Schema Docs: null/1 - No service HTTP API.
- Database Schema: null/1 - No application database.

**Dev Environment**
- VCS CLI Tools: 1/1 - `gh` is installed and authenticated.
- Agentic Development: 1/1 - Copilot guidance and an agent skill are present.
- Single Command Setup: 1/1 - README documents `uv sync` and CLI examples.
- Devcontainer: 0/1 - No devcontainer configuration.
- Environment Template: 1/1 - Optional write credentials are documented.
- Local Services Setup: null/1 - No required local service.
- Devcontainer Runnable: null/1 - Devcontainer CLI is unavailable.

**Debugging & Observability**
- Structured Logging: 0/1 - Human-readable logging only.
- Distributed Tracing: 0/1 - No trace or request-ID propagation.
- Metrics Collection: 0/1 - No application metrics instrumentation.
- Code Quality Metrics: null/1 - No local metrics gate; admin-only remote checks are unavailable.
- Contextual Error Tracking: 0/1 - No configured error tracker.
- Alerting: 0/1 - No alert rules or notification integration.
- Deployment Observability: 0/1 - No deploy-impact dashboard or annotation.
- Health Checks: null/1 - Not a long-running service.
- Circuit Breakers: 1/1 - External reads use exponential-backoff retries.
- Profiling Instrumentation: 0/1 - No profiling infrastructure.
- Product Analytics: 0/1 - No usage analytics instrumentation.
- Error-to-Insight Pipeline: 0/1 - No error-to-issue automation.

**Security**
- Branch Protection: null/1 - Authenticated account lacks repository admin access.
- Secret Scanning: null/1 - No local scanner; native scanning cannot be verified without admin access.
- CODEOWNERS: 0/1 - No `CODEOWNERS` file.
- Automated Security Review: null/1 - No local reporting; code scanning cannot be verified without admin access.
- Dependency Update Automation: 0/1 - No Dependabot or Renovate configuration.
- Gitignore Comprehensive: 0/1 - `.env` and common IDE folders are not excluded.
- Privacy Compliance: null/1 - No end-user account data collection.
- Secrets Management: 1/1 - S3 write credentials use environment variables, profiles, or roles.
- Minimum Release Age: 0/1 - No dependency-age policy.
- DAST Scanning: null/1 - No staged web service.
- PII Handling: null/1 - No personal-data processing.
- Log Scrubbing: 0/1 - No redaction mechanism or policy.

# Action Items
- Add a root `AGENTS.md` with verified setup and test commands, and add pre-commit Ruff checks.
- Make the documented development setup reliably collect tests, then enforce a coverage threshold.
- Reduce PR feedback time by splitting or optimizing the multi-platform CI matrix.

---
View the full report: https://app.factory.ai/analytics/readiness/https%253A%252F%252Fgithub.com%252Fucam-eo%252Fgeotessera

########## supabase/supabase ##########
📊 Starting agent readiness evaluation for: https://github.com/supabase/supabase.git
# Level
**Level 3**, 49.8% across 81 evaluated criteria. The report was stored for commit `fdab2cc7`. Three criteria were skipped.

# Applications
1. `apps/design-system` - Next.js design-system reference and component demos
2. `apps/docs` - Next.js documentation site and API routes
3. `apps/kb` - Astro knowledge base and search site
4. `apps/learn` - Next.js course and learning site
5. `apps/lite-studio` - React Router lightweight Studio application
6. `apps/studio` - Project and database management dashboard
7. `apps/ui-library` - Next.js UI block registry and documentation site
8. `apps/www` - Main marketing website
9. `docker` - Self-hosted Supabase service stack
10. `supabase/functions/og-images` - Open Graph image Edge Function
11. `supabase/functions/search-embeddings` - Documentation search embeddings Edge Function

# Criteria

**Style & Validation**
- Large file detection: 0/1 - No size threshold or LFS rule.
- Tech debt tracking: 0/1 - No enforced debt-marker tracking.
- Lint config: 6/11 - Six apps configure ESLint.
- Type check: 10/11 - All but the Docker stack have static typing.
- Formatter: 8/11 - Prettier covers apps, not Docker or the Edge Functions.
- Pre-commit hooks: 0/11 - No checked-in quality hooks.
- Strict typing: 7/11 - Seven apps enable strict checking.
- Naming consistency: 1/11 - Studio documents explicit conventions.
- Cyclomatic complexity: 0/11 - No complexity gate.
- Dead code detection: 8/11 - Knip covers pnpm apps.
- Duplicate code detection: 0/11 - No duplication detector.
- Code modularization: 0/11 - No enforced dependency boundaries.

**Build System**
- Build command documented: 1/1 - `AGENTS.md` lists build commands.
- Dependencies pinned: 1/1 - Lockfile and pinned tooling are committed.
- VCS CLI tools: 1/1 - GitHub CLI is installed and authenticated.
- Automated PR review: 1/1 - CodeRabbit posts reviews.
- Agentic development: 1/1 - Agent instructions, skills, and review guidance exist.
- Fast CI feedback: 0/1 - Sampled merged PR checks averaged 14.8 minutes, above the 10-minute target.
- Build performance tracking: 1/1 - Caching and parallel test shards are configured.
- Deployment frequency: 0/1 - Multiple successful production deployments per week were not verified.
- Single-command setup: 1/1 - Developer instructions provide a short path to a running site.
- Feature flag infrastructure: 1/1 - ConfigCat and PostHog are configured.
- Release notes automation: 0/1 - No automated release-note generator found.
- Progressive rollout: 1/1 - Feature flags support staged exposure.
- Rollback automation: 0/1 - No automated rollback path found.
- Monorepo tooling: 1/1 - pnpm workspaces and Turborepo are configured.
- Heavy dependency detection: 3/11 - Three apps configure bundle analysis.
- Unused dependencies detection: 8/11 - Knip covers pnpm apps.
- Version drift detection: 0/1 - The catalog does not reject workspace drift.
- Release automation: 1/1 - Image publishing and function deployment are automated.
- Dead feature flag detection: 0/1 - No stale-flag check found.

**Testing**
- Unit tests exist: 5/11 - Five apps have Vitest tests.
- Integration tests exist: 5/11 - Four apps have Playwright suites; Docker has smoke tests.
- Unit tests runnable: 0/11 - Bounded Vitest collection failed because local dependencies are absent. No tests were executed.
- Test performance tracking: 4/11 - CI retains coverage or Playwright reports.
- Flaky test detection: 4/11 - CI retries are configured.
- Test coverage thresholds: 0/11 - No enforced minimum found.
- Test naming conventions: 2/11 - Two Vitest configs specify test-file patterns.
- Test isolation: 6/11 - Parallel or isolated test configurations exist.
- Interactive QA exists: 8/11 - Eight apps have complete documented paths.
- Interactive QA runnable: 8/11 - Eight pass by documented fallback; live QA was not run.

**Documentation**
- AGENTS.md: 1/1 - Root agent guidance covers commands and conventions.
- README: 1/1 - Root README provides platform and development pointers.
- Automated doc generation: 1/1 - Docs and KB generate reference or Markdown output.
- Skills: 1/1 - Valid, substantive skills are checked in.
- Documentation freshness: 1/1 - Key guidance changed within 180 days.
- API schema docs: 8/11 - A GraphQL schema and API specifications are present.
- Service flow documented: 1/1 - README includes an architecture diagram.
- AGENTS.md validation: 0/1 - No automation checks its commands or references.

**Dev Environment**
- Devcontainer: 0/1 - No devcontainer configuration.
- Environment template: 1/1 - Environment examples exist.
- Local services setup: 1/1 - Compose and Supabase CLI setup are documented.
- Database schema: 6/11 - Migrations describe six apps’ data.
- Devcontainer runnable: null/1 - Skipped; the CLI is unavailable.
- Runbooks documented: 0/1 - No incident runbook pointer found.

**Debugging & Observability**
- N+1 detection: 0/11 - No query-count or N+1 gate found.
- Structured logging: 3/11 - Three apps have dedicated logging setups.
- Distributed tracing: 2/11 - Studio and Docker have tracing evidence.
- Metrics collection: 4/11 - Four apps have telemetry or metrics integrations.
- Code quality metrics: 1/11 - Studio uploads coverage to Coveralls.
- Error tracking contextualized: 1/11 - Studio configures Sentry context and source maps.
- Alerting configured: 1/11 - Studio workflow failures alert Slack.
- Deployment observability: 0/11 - No deployment-impact dashboard pointer found.
- Health checks: 2/11 - Studio and Docker define checks.
- Circuit breakers: 4/11 - Four apps configure retry or backoff.
- Profiling instrumentation: 0/11 - No configured runtime profiler found.
- Product analytics instrumentation: 4/11 - Four apps use shared PostHog telemetry.
- Error-to-insight pipeline: 1/11 - Studio identifies its Sentry project.

**Security**
- Branch protection: null/1 - Skipped; authenticated access lacks admin rights.
- Secret scanning: null/1 - Skipped; no local scanner found and native settings require admin access.
- CODEOWNERS: 1/1 - Team ownership is defined.
- Automated security review: 1/1 - PR checks link to CodeQL and Semgrep scans.
- Dependency update automation: 1/1 - Dependabot is scheduled.
- Gitignore comprehensive: 0/1 - Environment-file exceptions leave gaps.
- DAST scanning: 1/11 - Docker CI tests running endpoints.
- PII handling: 4/11 - Consent controls cover four apps.
- Privacy compliance: 1/1 - Consent handling and a privacy policy exist.
- Secrets management: 1/1 - Workflows and scripts use managed secrets.
- Log scrubbing: 1/11 - Studio sanitizes sensitive log data.
- Minimum release age: 1/1 - pnpm enforces a three-day delay.
- Issue templates: 0/1 - No structured issue templates.
- Issue labeling system: 1/1 - Priority, type, and area labels exist.
- Backlog health: 1/1 - All 100 sampled open issues have descriptive titles and labels.
- PR templates: 1/1 - A structured PR template exists.

# Action Items
- Add pre-commit lint and formatting hooks, plus a coverage threshold.
- Reduce primary PR CI below 10 minutes through narrower jobs or improved caching.
- Add an automated release-note workflow and a documented rollback action.

---
View the full report: https://app.factory.ai/analytics/readiness/https%253A%252F%252Fgithub.com%252Fsupabase%252Fsupabase

```

## Part II: Analysis

**Which pillars failed most**, and were failures consistent across all three or specific to one?

Observability failed worst and failed everywhere: 0.0% (humanizer), 10.0% (geotessera), 16.1% (supabase). 
No repo passes structured logging, distributed tracing, or alerting, so there is nothing in any of them for an agent to read at runtime. 

Style & Validation is the next weakest and also fails across all three (9.1%, 15.4%, 30.3%), with pre-commit hooks, complexity limits, duplication checks, and dead-code/tech-debt tracking missing everywhere. 

Security is the exception that breaks the pattern: 7.7% and 16.7% for the two small repos but 68.2% for supabase, so that failure is specific to the small repos rather than general. 

**What explains the pattern?** Which suspects your data supports, and which it cannot distinguish:

One obvious thing is that smaller teams (humanizer and geotessera) vs a big corporation (supabase) have different amount of bandwidth and manpower to dedicate. The smaller teams are at Level-2; the Level-3 repo is corporate-backed with 11 applications and team-based CODEOWNERS. 

All other factors could be confounds, and probably don't explain the big differences in pillar scores. 


**Cheapest high-leverage fix**, per repo:

| Repo | The one change | Why this one, over the report's top suggestion |
|---|---|---|
| humanizer | Add a Ruff config plus a `.pre-commit-config.yaml` (lint and format) and a `.gitignore`, in one commit. |A single config file makes every future edit machine-checkable and satisfies three criteria at once (linter, formatter, pre-commit hooks). For a 14-file Markdown skill this is the smallest change that turns "no automated validation" into "every change is checked." |
| geotessera | Make the documented setup install the geospatial dependencies so `pytest` collects, then record that one command in a root `AGENTS.md`. | The report's #1 names `AGENTS.md`, but documentation alone does not fix the blocker. `unit tests runnable` scored 0/1 because collection failed on a missing `geopandas`; the agent could not run the suite at all, and `interactive QA runnable` only passed on a documentation fallback for the same reason. Adding an extras group so the install command actually pulls in `geopandas` is the executable half of the suggestion, and the `AGENTS.md` sentence is worthless until the command it documents works. |
| supabase | Add one root pre-commit configuration that runs the existing lint and format tools on changed files. | The report's #1 bundles pre-commit hooks with coverage thresholds. Pre-commit hooks is the one Style criterion every application misses (0/11) and is a Basic-difficulty signal. The coverage-threshold half would need per-app configuration across 11 applications and would fail CI on legacy gaps immediately.  |

**Where the framework falls short:**

- **You need access for security checks:** `branch protection` and `secret scanning` were skipped in all three because the authenticated account lacks admin access, so the two Security criteria an evaluator most wants are unverifiable from outside an org.
- **Doesn't work uniformly for big monorepos:** Application-scope scoring penalizes monorepos. Nothing weights by app importance or maturity, so a genuinely standardized repo shows 30.3% on Style & Validation because one peripheral app lacks a formatter (like for Supabase)
- **Documentation is tested on freshness, not correctness**
- **A pillar/subpillar's applicability to a repo is not measure well** a library (geotessera) or a skill (humanizer) don't need heavy production telemetry

## Submission
1. `Command (⌘) + F` for `TODO`. No results means you're done.
2. Push all changes to your remote repository and submit via Gradescope.
