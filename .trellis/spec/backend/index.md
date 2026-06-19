# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains the current backend development conventions for the
FastAPI backend, domain services, metadata persistence adapters, runtime
observability, and quality gates.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Database Guidelines](./database-guidelines.md) | Metadata backends, queries, schema bootstrap | Filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies, API error shape | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns, testing requirements | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels, sensitive-data rules | Filled |

---

## Pre-Development Checklist

Before backend changes:

1. Read [Directory Structure](./directory-structure.md) to choose the correct
   layer and ownership boundary.
2. Read [Error Handling](./error-handling.md) for any API, service, or workflow
   change that can fail.
3. Read [Database Guidelines](./database-guidelines.md) for persistence,
   repository, metadata, migration, or storage changes.
4. Read [Logging Guidelines](./logging-guidelines.md) for runtime,
   observability, worker, provider, or ops changes.
5. Read [Quality Guidelines](./quality-guidelines.md) before tests, release
   gates, or review.

These guidelines document observed project conventions from the current codebase
and existing dev docs. Update them when the implementation contract changes.

---

**Language**: All documentation should be written in **English**.
