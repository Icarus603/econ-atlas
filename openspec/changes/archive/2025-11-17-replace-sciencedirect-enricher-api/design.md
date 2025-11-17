# Design: Replace ScienceDirect Fallback Enricher with Elsevier API

## Overview
- Introduce `ElsevierApiClient` that wraps the relevant REST endpoints (likely Article Retrieval API) and handles auth header, retries, backoff, and HTTP errors.
- `ScienceDirectFallbackEnricher` becomes `ScienceDirectApiEnricher` that first attempts `ElsevierApiClient.fetch(pi)`; on success it maps JSON into `ArticleRecord` fields and runs translation as today. If the API call raises an unrecoverable error (HTTP 4xx/5xx after retries) or the API key is missing, it logs the reason and optionally invokes the existing DOM parser as a slow fallback.
- `Runner` keeps the same contract; only the enrichment implementation changes.

## Key Considerations
1. **Configuration**
   - Add `ELSEVIER_API_KEY` (and optional host override). Validate at startup; warn when missing.
   - Keep ScienceDirect-specific `.env` fields for the legacy fallback (cookies/profile) so operators can still opt in.
2. **Rate limiting & Retries**
   - Respect Elsevier default quota (e.g., 20 req/sec). Implement client-side throttling (simple sleep or token bucket) and exponential backoff on 429/5xx.
   - Surface metrics/logs when API requests fail repeatedly.
3. **Field Mapping**
   - Map JSON output (`coredata/title`, `dc:creator`, `prism:doi`, `prism:coverDate`, `dc:description`) into our `ArticleRecord`. Document mapping in parser profile.
4. **Fallback Strategy**
   - When API is unavailable, drop back to the existing fallback DOM parser so we still capture basic fields. Ensure both paths share translation logic.
5. **Testing**
   - Mock the API client to simulate success/429/403.
   - Runner tests verifying translation counters, logging, and fallback triggers.
