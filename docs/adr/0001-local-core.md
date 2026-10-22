# ADR 0001: Start with a small shared local core

Status: accepted for version 0.1.0.

## Context

The core must work without a hosted account or a desktop client. Identity, source authority, reviewed operating instructions and recovery need concrete behavior before connector breadth and visualization.

## Decision

Use Python 3.11+, SQLite canonical storage, explicit modular services and one shared authorization path. Keep files as retained text inside the initial database so SQLite backup can capture a coherent state. Use lexical retrieval initially and isolate provider extraction behind a small interface. Use authenticated encryption from the maintained cryptography library rather than designing encryption.

Expose a local CLI, a small REST adapter and MCP stdio. Keep operator filesystem/recovery methods out of public RPC. Treat source material as data, policies/skills as reviewed artifacts and action execution as a separate runtime concern.

## Consequences

Developers can run and inspect the project with a small dependency set. The initial release is bounded in source formats, snapshot size, search quality and deployment throughput. Larger storage, semantic retrieval, remote identity and recording support require explicit tested extensions. The public API and documented evidence boundaries make those additions reviewable.
