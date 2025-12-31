---
title: Roadmap
description: Project milestones, planned features, backlog items, and risk register
version: 1.0.0
last_updated: 2025-12-30
related: [README.md, architecture.md, changelog.md]
tags: [roadmap, planning, features, risks]
---

# Roadmap

## Table of Contents

- [Current State](#current-state)
- [Milestones](#milestones)
- [Feature Backlog](#feature-backlog)
- [Technical Debt](#technical-debt)
- [Risk Register](#risk-register)

## Current State

### Version: Workshop v1.0

**Status**: Learning/Workshop Project - Core functionality complete, production features pending

**Completed** ✅:
- Multi-MCP integration (HTTP, stdio)
- Recursive tool calling loop
- Streaming and non-streaming responses
- Redis conversation persistence
- Basic web UI (index.html)
- Health check endpoints
- CORS configuration for local development

**In Progress** 🔄:
- Documentation (this docs/ folder)

**Blocked** 🚫:
- Production deployment (requires auth, PII handling)

## Milestones

### Milestone 1: Workshop Foundation ✅ COMPLETE

**Target**: 2025-Q4 (Completed)

**Objectives**:
- [x] Implement core agent pattern
- [x] Connect to 3 MCP servers
- [x] Implement streaming chat
- [x] Add Redis persistence
- [x] Create simple web UI

**Deliverables**:
- Working agent with tool calling
- Docker Compose setup
- Basic documentation

---

### Milestone 2: Production Readiness 🎯 PLANNED

**Target**: 2026-Q1

**Objectives**:
- [ ] Implement PII detection and redaction (Additional Task)
- [ ] Add authentication & authorization
- [ ] Implement comprehensive error handling
- [ ] Add retry logic for external services
- [ ] Proper MCP client cleanup on shutdown
- [ ] Configuration management (not env vars)

**Deliverables**:
- PII detection module
- Auth integration (OAuth2/JWT)
- Production-ready deployment guide
- Updated ADRs

**Success Criteria**:
- Zero PII leakage in logs/responses
- All endpoints require authentication
- 99.9% uptime in test environment

---

### Milestone 3: Testing & Quality 📊 PLANNED

**Target**: 2026-Q2

**Objectives**:
- [ ] Unit test coverage >80%
- [ ] Integration tests for key flows
- [ ] E2E browser tests (Playwright)
- [ ] CI/CD pipeline (GitHub Actions/GitLab CI)
- [ ] Performance benchmarking

**Deliverables**:
- `tests/` directory with pytest suite
- CI pipeline configuration
- Performance baseline report
- Test data fixtures

**Success Criteria**:
- All tests pass in CI
- Test suite runs <5 minutes
- Coverage report published

---

### Milestone 4: Observability 🔭 PLANNED

**Target**: 2026-Q3

**Objectives**:
- [ ] Structured logging (JSON format)
- [ ] Metrics collection (Prometheus)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Monitoring dashboards (Grafana)
- [ ] Alerting rules

**Deliverables**:
- Logging configuration
- Metrics exporters
- Trace instrumentation
- Dashboard templates
- Runbook for common issues

**Success Criteria**:
- All tool calls traced end-to-end
- P95 latency < 5s (excl. LLM inference)
- Alerts fire before user reports

---

### Milestone 5: Advanced Features ⚡ FUTURE

**Target**: 2026-Q4

**Objectives**:
- [ ] Parallel tool execution
- [ ] Conversation summarization
- [ ] Multi-user support
- [ ] Conversation search
- [ ] Tool result caching
- [ ] Alternative LLM providers

**Deliverables**:
- Parallel executor
- Summarization agent
- User session management
- Search index (Elasticsearch?)

**Success Criteria**:
- Tool calls execute concurrently where possible
- Long conversations don't degrade performance
- Search finds relevant conversations <100ms

---

## Feature Backlog

### High Priority

| Feature | Category | Effort | Value | Status |
|---------|----------|--------|-------|--------|
| **PII Detection** | Security | M | High | TODO |
| Authentication | Security | L | High | TODO |
| MCP Client Cleanup | Reliability | S | Medium | TODO |
| Retry Logic | Reliability | M | Medium | TODO |
| Error Handling | Reliability | M | Medium | TODO |

#### PII Detection (Additional Task)

**Rationale**: Agent handles user data (names, emails, potentially credit cards). Must prevent PII disclosure.

**Approach**:
1. Integrate PII detection library (e.g., Presidio, AWS Comprehend)
2. Scan messages before sending to LLM
3. Scan tool results before returning to user
4. Redact detected PII (replace with `[REDACTED_EMAIL]`, etc.)
5. Log PII detections for audit

**Acceptance Criteria**:
- Credit card numbers detected and redacted
- Email addresses preserved when needed, redacted when inappropriate
- SSN, phone numbers redacted
- Configurable sensitivity levels

**Code Changes**:
- Add `agent/pii_detector.py` module
- Integrate in `ConversationManager.chat()` and `DialClient._call_tools()`
- Add configuration for redaction rules

---

#### Authentication

**Rationale**: Open API is insecure; production requires user identification.

**Approach**:
- OAuth2 + JWT tokens
- FastAPI dependency for auth middleware
- User-specific conversation isolation

**Acceptance Criteria**:
- All endpoints except `/health` require auth
- Conversations scoped to user ID
- Invalid tokens return 401

---

### Medium Priority

| Feature | Category | Effort | Value | Status |
|---------|----------|--------|-------|--------|
| Unit Tests | Quality | L | Medium | TODO |
| Conversation Summarization | UX | M | Medium | TODO |
| Parallel Tool Execution | Performance | L | Medium | TODO |
| Configuration Management | DevOps | M | Low | TODO |
| API Rate Limiting | Reliability | S | Low | TODO |

#### Conversation Summarization

**Rationale**: Long conversations exceed context window and slow down responses.

**Approach**:
- Trigger summarization when message count > threshold (e.g., 50)
- Use LLM to summarize history into condensed context
- Keep recent N messages + summary
- Store original messages for audit

**Acceptance Criteria**:
- Conversations >50 messages maintain <5s response time
- Summaries preserve key context (user intents, tool results)
- Original messages retrievable via API

---

#### Parallel Tool Execution

**Rationale**: Sequential tool calls increase latency.

**Approach**:
- Detect independent tool calls (no data dependencies)
- Execute in parallel using `asyncio.gather()`
- Maintain order in results for deterministic LLM input

**Acceptance Criteria**:
- Multiple `search_users` calls execute concurrently
- Total latency reduced by ~50% for multi-tool scenarios
- No race conditions or data corruption

---

### Low Priority

| Feature | Category | Effort | Value | Status |
|---------|----------|--------|-------|--------|
| E2E Tests | Quality | L | Low | TODO |
| Conversation Search | UX | M | Low | TODO |
| Alternative MCP Servers | Integration | S | Low | TODO |
| Multi-Model Support | Features | M | Low | TODO |
| Tool Result Caching | Performance | M | Low | TODO |

---

## Technical Debt

### Code Quality

| Issue | Impact | Priority | Planned Fix |
|-------|--------|----------|-------------|
| No automated tests | High | High | Milestone 3 |
| Global state (conversation_manager) | Medium | Medium | Refactor to dependency injection |
| Missing type hints in some functions | Low | Low | Gradual addition |
| Hardcoded URLs in app.py | Medium | Medium | Configuration management |
| No logging configuration | Medium | Medium | Milestone 4 |

### Documentation Debt

| Issue | Impact | Priority | Status |
|-------|--------|----------|--------|
| Missing ADRs for key decisions | Medium | High | In Progress (this milestone) |
| No contributor guide | Low | Low | TODO |
| API examples incomplete | Medium | Medium | Partially addressed in api.md |

### Infrastructure Debt

| Issue | Impact | Priority | Planned Fix |
|-------|--------|----------|-------------|
| No CI/CD pipeline | High | High | Milestone 3 |
| No monitoring/alerting | High | High | Milestone 4 |
| Redis single-point-of-failure | Medium | Low | Not planned (workshop project) |
| No backup/restore procedures | Medium | Low | Not planned (workshop project) |

---

## Risk Register

### Technical Risks

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| **LLM API rate limits** | Medium | High | Implement retry with backoff, queue requests | Monitoring |
| **MCP server downtime** | Medium | High | Health checks, fallback to cached tools | TODO |
| **Redis data loss** | Low | High | Enable AOF, regular backups | Partial (AOF enabled) |
| **Infinite tool calling loop** | Low | High | Max recursion depth limit | Relies on LLM |
| **PII leakage** | High | Critical | PII detection (Milestone 2) | TODO |
| **Token context overflow** | Medium | Medium | Summarization (backlog) | TODO |

### Operational Risks

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| **DIAL API unavailable** | Low | Critical | Monitor health, alert on failures | TODO |
| **Docker daemon crash** | Low | High | Use Kubernetes for production | Not planned |
| **Redis memory exhaustion** | Medium | High | Set maxmemory, use LRU eviction | Configured |
| **Uncontrolled costs** | Medium | High | Monitor API usage, set quotas | TODO |

### Security Risks

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| **No authentication** | N/A | Critical | Implement auth (Milestone 2) | Known limitation |
| **Open CORS policy** | N/A | High | Restrict origins in production | Development only |
| **Secrets in env vars** | Medium | High | Use secret manager (Milestone 2) | TODO |
| **SQL injection in UMS** | Low | Medium | UMS is mock service, not production | Accepted |
| **XSS in frontend** | Low | Medium | Content Security Policy, input sanitization | TODO |

### Dependency Risks

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| **MCP protocol changes** | Medium | High | Pin fastmcp version, monitor updates | TODO |
| **DIAL API breaking changes** | Low | High | Version API calls, integration tests | TODO |
| **Redis deprecation** | Low | Medium | Abstract persistence layer | Not planned |
| **Python 3.11 EOL** | Low | Low | Plan upgrade to 3.12+ | Monitoring |

---

## Decision Log

### Recent Decisions

- **2025-12-30**: Documentation milestone prioritized over production features (educational focus)
- **2025-12-30**: PII detection deferred to Milestone 2 (complexity > initial scope)
- **2025-12-30**: Redis clustering not planned (workshop project, not production)

### Upcoming Decisions

- **Q1 2026**: Choose PII detection library (Presidio vs AWS Comprehend vs custom)
- **Q1 2026**: Select auth provider (Auth0 vs Keycloak vs custom JWT)
- **Q2 2026**: CI/CD platform (GitHub Actions vs GitLab CI vs Jenkins)

---

## Version History

| Version | Date | Milestone | Key Changes |
|---------|------|-----------|-------------|
| Workshop v1.0 | 2025-12-30 | M1 Complete | Initial workshop implementation |
| v1.1 (planned) | 2026-Q1 | M2 | PII detection, authentication |
| v2.0 (planned) | 2026-Q2 | M3 | Test coverage, CI/CD |
| v3.0 (planned) | 2026-Q3 | M4 | Observability |

---

## Contributing to Roadmap

**Suggest features**: Open GitHub issue with `enhancement` label

**Propose changes**: Submit PR to this roadmap.md

**Prioritization**: Based on educational value, production necessity, and effort/value ratio

---

**Next Steps**: Review [Changelog](./changelog.md) for detailed version history or consult [ADR Index](./adr/README.md) for architecture decisions.
