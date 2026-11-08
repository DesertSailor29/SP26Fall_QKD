# Project plan: QKD with Kerberos-authenticated classical channel

**Team:** 6 · **Duration:** 6 weeks (deadline ≈ 2026-12-08) · **Effort:** ~4 h of focused work per person per day

## 1. Goal

QKD needs an authenticated classical channel. The textbook solution is pre-shared keys (PSK) with
Wegman–Carter authentication. It is information-theoretically secure, but n users need n(n−1)/2
pairwise keys, and every authenticated message uses up key material.

We test whether **Kerberos** can replace the pairwise pre-shared keys: n long-term keys held by one
Key Distribution Center (KDC) instead of n² pairwise keys. We then measure and analyse what this gains
(speed, storage, scaling) and what it costs in security (a trusted KDC, and only computational security).

**Deliverables**

1. A working prototype with swappable authentication: **A) PSK + Wegman–Carter** and **B) Kerberos-lite**.
2. Measurements comparing A and B, plus a scaling model up to large numbers of nodes.
3. A structured threat analysis (STRIDE + attack trees). A formal protocol model is a stretch goal.
4. A report and a presentation.

**Stretch goals** (only if they don't put the deliverables above at risk): **C) PQC signature
authentication**, real MIT Kerberos in place of Kerberos-lite, and a Tamarin/ProVerif model.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ Benchmark harness: scenarios, metrics, scaling model, plots         │
├─────────────────────────────────────────────────────────────────────┤
│ Auth layer (swappable)    A) PSK+Wegman–Carter │ B) Kerberos-lite │ C) PQC │
├─────────────────────────────────────────────────────────────────────┤
│ Classical channel: message transport + simulated latency            │
├─────────────────────────────────────────────────────────────────────┤
│ KMS: ETSI GS QKD 014-style key store and API                        │
├─────────────────────────────────────────────────────────────────────┤
│ Quantum layer: BB84 model → sifting → error correction → privacy amp│
└─────────────────────────────────────────────────────────────────────┘
```

QKD post-processing (basis sifting, error-correction parities, the privacy-amplification seed) sends
classical messages, and those messages **must** be authenticated. The quantum layer therefore sends
everything through `AuthenticatedChannel`, so changing the authenticator is the only difference between
variants A, B and C.

The quantum layer is a **model**, not a physical simulation. It produces keys with a configurable error
rate (QBER), loss and an optional intercept-resend eavesdropper. Physical realism is out of scope.

Language: Python 3.12. Libraries: `numpy`, `cryptography` (AES-GCM, HMAC), `fastapi` (KMS API),
`pytest`, and `liboqs-python` for the stretch goal.

## 3. Interfaces: the contract between workstreams

The full specification is in [INTERFACES.md](INTERFACES.md). It is **frozen at the end of week 1**. After
that, a change needs agreement from every owner whose code uses the interface. Every component ships
with:

- an implementation behind the interface,
- a **mock** that other workstreams can develop against from day 1,
- contract tests in `tests/contract/` that both the real component and the mock pass.

The four interfaces:

| Interface | Provided by | Used by |
|---|---|---|
| `KeySource` (QKD link → key blocks) | Quantum layer | KMS |
| `KeyStore` + ETSI-014 REST API | KMS | Auth layer (PSK refill), applications, benchmarks |
| `Authenticator` / `AuthenticatedChannel` | Auth layer | Quantum layer (post-processing), benchmarks |
| `MetricsSink` (JSONL event records) | Benchmark harness | Everyone |

## 4. Workstreams and owners

| # | Workstream | Scope | Load |
|---|---|---|---|
| WS1 | Quantum layer | BB84 model, sifting, QBER estimate, error correction (simplified Cascade), Toeplitz privacy amplification, Eve model | M |
| WS2 | KMS + channel + integration lead | KeyStore, ETSI-014 subset, transport with latency model, end-to-end wiring, CI | M–L |
| WS3 | Auth A: PSK + Wegman–Carter | Universal hash + OTP tags, key-pool consumption, refill from QKD output, pairwise key provisioning | S–M (also helps WS5) |
| WS4 | Auth B: Kerberos-lite | KDC (AS + TGS), tickets, authenticators, replay protection, session keys → MAC; later real Kerberos | L |
| WS5 | Benchmarks + scaling | Scenarios, metrics collection, analytic scaling model, many-node simulation, plots | M |
| WS6 | Threat analysis + report lead | System model, STRIDE per component, attack trees, comparison of A vs B (vs C); report structure | M |

Assign people as you see fit. WS2 and WS6 also coordinate the team, so they work best with people who
like integrating things and writing.

## 5. Timeline

| Week | Dates | Milestone |
|---|---|---|
| 1 | 10-27 → 11-02 | Repo skeleton, CI, **INTERFACES.md frozen**, mocks for every interface, threat-analysis system model |
| 2 | 11-03 → 11-09 | Components work standalone against mocks; contract tests green |
| 3 | 11-10 → 11-16 | Components feature-complete; first end-to-end run of **variant A** |
| 4 | 11-17 → 11-23 | **Variant B end-to-end**; benchmark harness runs both variants; STRIDE complete |
| 5 | 11-24 → 11-30 | Measurement campaign, scaling results, attack trees; stretch goals only if weeks 1–4 are on track |
| 6 | 12-01 → 12-08 | **Code freeze on 12-03**, then the report, presentation and buffer |

Check-ins: a 15-minute stand-up every day, and on Fridays an integration session that runs everything
on `main`.

## 6. Metrics

Every component logs events through `MetricsSink`. These metrics are collected for each variant:

| Metric | Definition |
|---|---|
| Key establishment time | From "start QKD session" until a final key is stored in the KMS |
| Auth cost per message | CPU time, plus round trips × simulated latency |
| Pair setup time | First contact between two nodes that have never talked (B: TGS + AP exchange) |
| Onboarding cost | Steps, messages and out-of-band installs needed to add node n+1 |
| Storage | Bytes of key material per node, and at the KDC |
| Key consumption | QKD key bits used for authentication per block of final key |
| Messages | Classical messages and bytes per QKD session |
| KDC load | Requests/s the KDC must handle as n grows (B only) |

Time is reported in two parts, **CPU time** (measured) and **network time** (round trips × configurable
RTT). On one machine, wall-clock time would hide the round-trip cost.

Scaling: an analytic model (e.g. PSK storage O(n²) in total vs. Kerberos O(n)) is checked against
simulations at n = 2, 10, 100, 1000.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Integration fails late | Interfaces frozen in week 1, mocks from day 1, contract tests, weekly integration session |
| Kerberos-lite grows too big | Use a minimal protocol (AS/TGS/AP, no realms or cross-realm, no pre-auth variants); real Kerberos is a stretch goal |
| Error correction takes too long | Fallback: model leakage as f·h(QBER)·n bits without real Cascade |
| Comparing A and B is unfair because their security levels differ | State this explicitly; it's a finding of the threat analysis, not a bug |
| Someone is unavailable | Every workstream has a mock, so the others are never blocked |
