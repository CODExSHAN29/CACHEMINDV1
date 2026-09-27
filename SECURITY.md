# Security Policy

CacheMind is designed as an enterprise security and inference caching gateway. We take vulnerability reports and security issues seriously.

---

## 🛡️ Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in CacheMind, please report it privately:

1. **Do not open a public GitHub issue.**
2. Send an email to **`security@cachemind.dev`** or contact the repository maintainers via GitHub Security Advisories.
3. Include detailed steps to reproduce the vulnerability, along with relevant logs, payloads, or proof of concepts.

---

## 🔒 Security Architecture Highlights

- **Server-Side Identity Derivation**: Client headers (`X-Tenant-ID`, `X-Org-ID`) are untrusted; tenant identity is cryptographically derived from verified SHA-256 API key hashes.
- **Ingress PII Sanitization**: High-throughput regex & Luhn checksum scanning masks credit cards, SSNs, emails, phone numbers, and secret tokens before embedding, caching, or upstream transmission.
- **Multi-Tenant Isolation**: Exact hash keys and vector search spaces are hard-partitioned by `(tenant_id, project_id)`.
- **Fail-Open Resilience**: Cache backend downtime falls open gracefully to upstream providers rather than failing client inference.
