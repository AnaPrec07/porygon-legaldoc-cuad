# Requirements: MCP PII/PHI De-identification Server

**System:** `porygon-legaldoc-cuad` — MCP Server
**Version:** 1.0 | **Date:** April 2025

---

## Table of Contents

1. [Business Requirements](#1-business-requirements-brs)
2. [Functional Requirements](#2-functional-requirements-frs)
3. [Non-Functional Requirements](#3-non-functional-requirements-nfrs)

---

## 1. Business Requirements (BRs)

These capture *why* the system exists — the organizational and strategic intent.

| ID | Requirement |
|----|-------------|
| BR-01 | The organization must process legal and healthcare documents containing sensitive personal information without exposing raw PII/PHI to downstream consumers, AI models, or storage systems. |
| BR-02 | De-identified data must remain analytically useful — i.e., the same entity (person, date, ID) must consistently map to the same token, preserving correlations across documents. |
| BR-03 | The system must support re-identification by authorized parties, ensuring that de-identification is reversible under controlled access — not a one-way hash. |
| BR-04 | The solution must integrate with AI agent pipelines (MCP-compatible clients, ADK agents) as a reusable, callable tool rather than a standalone batch job. |
| BR-05 | All cryptographic material must be managed centrally and never embedded in source code or containers. |
| BR-06 | The system must be operable on GCP infrastructure to comply with existing organizational cloud strategy. |

---

## 2. Functional Requirements (FRs)

These describe *what* the system does — concrete behaviors and capabilities.

### Document Ingestion

| ID | Requirement |
|----|-------------|
| FR-01 | The system shall accept a PDF document as raw bytes via the `get_masked_text` MCP tool. |
| FR-02 | The system shall support `application/pdf` as the default MIME type, with the architecture allowing extension to other types (`image/png`, etc.). |
| FR-03 | The system shall extract full text from the document using GCP Document AI OCR via a pre-configured processor (`e5822741a51eeb33`, location `us`). |

### PII/PHI Detection & De-identification

| ID | Requirement |
|----|-------------|
| FR-04 | The system shall detect and de-identify the following info types: `PERSON_NAME`, `DATE_OF_BIRTH`, `AGE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `STREET_ADDRESS`, `LOCATION`, `US_SOCIAL_SECURITY_NUMBER`, `US_PASSPORT`, `US_DRIVERS_LICENSE_NUMBER`, `US_HEALTHCARE_NPI`, `US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER`, `MEDICAL_RECORD_NUMBER`, `US_MEDICARE_BENEFICIARY_ID_NUMBER`, `DATE`, `IP_ADDRESS`. |
| FR-05 | The system shall use `CryptoDeterministicConfig` (not random masking) so that identical plaintext values always produce identical tokens within the same key context. |
| FR-06 | De-identified tokens shall carry a `[DEIDENTIFIED]` surrogate type prefix to make them identifiable and re-identifiable in downstream processing. |
| FR-07 | The minimum detection likelihood threshold shall be set to `POSSIBLE` to maximize recall in sensitive document contexts. |
| FR-08 | The system shall support re-identification: given masked text containing `[DEIDENTIFIED]` surrogate tokens, the system shall restore original plaintext values using the same KMS-wrapped key. |

### Cryptographic Key Management

| ID | Requirement |
|----|-------------|
| FR-09 | The system shall load the KMS-wrapped AES-256 data encryption key from GCP Secret Manager at runtime (secret name: `kms_wrapped_key`). |
| FR-10 | The KMS key used to wrap/unwrap shall be `projects/porygon-legaldoc-cuad/locations/global/keyRings/dlp-keyring/cryptoKeys/dlp-key`. |
| FR-11 | The system shall base64-decode the secret payload before passing it to the DLP API as `KmsWrappedCryptoKey`. |

### MCP Server & Deployment

| ID | Requirement |
|----|-------------|
| FR-12 | The system shall expose the de-identification capability as an MCP tool named `get_masked_text` using the `streamable-http` transport. |
| FR-13 | The server shall expose an ASGI app object (`app`) for lifecycle management by an external process manager (uvicorn), not rely on `mcp.run()`. |
| FR-14 | The server shall read the `PORT` environment variable and default to `8080` if not set. |
| FR-15 | The system shall gracefully close the shared `httpx.AsyncClient` on shutdown. |

---

## 3. Non-Functional Requirements (NFRs)

These describe *how well* the system must perform — quality attributes.

### Security

| ID | Requirement |
|----|-------------|
| NFR-01 | Cryptographic keys shall never appear in source code, environment variables, or container images; they shall be retrieved exclusively from Secret Manager at runtime. |
| NFR-02 | The DLP client shall operate in `global` location for de-identification, consistent with the KMS key location, to avoid cross-region key access failures. |
| NFR-03 | `include_quote: False` must be enforced in the inspect config to prevent raw PII from appearing in DLP API audit logs or responses. |
| NFR-04 | Re-identification capability shall be access-controlled at the infrastructure layer (IAM); the MCP server itself shall not enforce caller authorization beyond GCP ADC. |

### Reliability & Correctness

| ID | Requirement |
|----|-------------|
| NFR-05 | The `deidentify_text` method shall raise `ValueError` for empty or whitespace-only input rather than sending an empty payload to the DLP API. |
| NFR-06 | The Document AI client shall be instantiated at module load time (not per-request) to avoid repeated authentication overhead. |
| NFR-07 | The system shall propagate `google.api_core.exceptions.GoogleAPICallError` to callers without swallowing it, allowing MCP clients to handle failures gracefully. |

### Maintainability

| ID | Requirement |
|----|-------------|
| NFR-08 | The list of detected info types shall be centrally defined as a single class-level attribute (`builtin_infotypes`) and not duplicated across `deidentify_text` and `reidentify_text`. |
| NFR-09 | `reidentify_text` shall use the proto-based `ReidentifyConfig` type consistently — the current dict-based construction is a technical debt item to be resolved before production. |
| NFR-10 | Module-level GCP client instantiation in `documentai.py` and `gcs.py` shall be evaluated for Cloud Run cold-start impact; lazy initialization should be considered if start times exceed SLA. |

### Observability

| ID | Requirement |
|----|-------------|
| NFR-11 | All GCS upload operations shall emit structured log entries via the existing `logger.info` call, including the blob path. |
| NFR-12 | The MCP server shall emit startup and shutdown log events to enable Cloud Run instance lifecycle monitoring. |
| NFR-13 | DLP transformation statistics from the `DeidentifyContentResponse` (available but currently unused) should be logged for audit and coverage monitoring in a future iteration. |

### Scalability & Performance

| ID | Requirement |
|----|-------------|
| NFR-14 | The shared `httpx.AsyncClient` shall be reused across requests to avoid per-request connection overhead. |
| NFR-15 | The system shall be stateless across requests — no in-memory caching of de-identified content — to support horizontal scaling on Cloud Run. |

---

## Technical Debt & Known Issues

| ID | Item | Priority |
|----|------|----------|
| TD-01 | `reidentify_config` in `reidentify_text` is constructed as a plain `dict` while `deidentify_config` uses proper proto types. This inconsistency may cause a runtime error or silent failure and must be resolved before production. | High |
| TD-02 | `response.overview.transformation_summaries` from the DLP `DeidentifyContentResponse` is available but unused. Logging this field would provide audit trail coverage for healthcare/legal document pipelines. | Medium |
| TD-03 | Module-level GCP client instantiation (`docai_client`, `gcs_client`) has not been benchmarked for Cloud Run cold-start impact. Lazy initialization should be evaluated if cold-start latency becomes an issue. | Low |
