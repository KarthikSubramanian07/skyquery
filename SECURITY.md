# Security Policy

## Supported versions

Security fixes are applied to the latest release on `main`.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Email **karthik [dot] subramanian [at] berkeley [dot] edu** with:

- A description of the issue and its impact
- Steps to reproduce, or a proof of concept
- Affected version / commit if known

You should receive an acknowledgment within a few days. Please give a reasonable window for a fix before any public disclosure.

## Scope notes

SkyQuery is a **local** MCP server and CLI. It stores optional free API keys (ADS, NASA) in the OS keychain and defaults to offline fixture replay. Reports involving credential leakage in logs/exceptions, SSRF via TAP URLs, or unbounded query parameters are especially welcome.
