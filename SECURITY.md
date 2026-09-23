# Security policy

## Scope

This repository contains experimental local runtime code. The supported default is a single-user process on the local machine or phone. The included HTTP server is not an authenticated public service.

## Safe defaults

- Bind the server to `127.0.0.1` unless a reviewed transport and access-control design exists.
- Keep save files, audio, exported vessels, and logs outside version control.
- Do not add credentials or personal data to issues, pull requests, fixtures, or notebooks.
- Do not implement remote execution by forwarding shell commands, Python expressions, or arbitrary paths.

## Reporting

For a suspected vulnerability, do not publish exploit details in a public issue. Contact the repository owner privately through the configured GitHub account and include the affected component, reproduction steps, impact, and a proposed mitigation.

## Future MCP/IPC work

A future bridge must be a narrow allowlisted protocol with explicit authentication, replay protection, input-size limits, timeouts, structured errors, and audit logging. The bridge should expose only approved operations such as `speak`, `learn`, `status`, and `save`; it must not expose the internal object graph or arbitrary filesystem and process access. Any implementation should ship with tests for unauthorized calls, malformed input, oversized input, path traversal, and shutdown behavior before network exposure is considered.
