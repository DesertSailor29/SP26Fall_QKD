# Backlog

Priority: **M**ust / **S**hould / **C**ould / **W**on't (this time). WS = workstream, see [PLAN.md](PLAN.md).
The week is the latest week an item should be done.

## Foundation (WS2, week 1)

| ID | Item | Prio | Wk |
|---|---|---|---|
| F1 | Repo skeleton: `src/qkdsim/`, `tests/`, `pyproject.toml`, ruff + pytest | M | 1 |
| F2 | CI (GitHub Actions): lint + tests on every PR | M | 1 |
| F3 | `interfaces.py` matching INTERFACES.md; agree on it and freeze | M | 1 |
| F4 | Mocks: `MockKeySource`, `InMemoryKeyStore`, `NullAuthenticator`, `ListMetricsSink` | M | 1 |
| F5 | Contract test suite per interface | M | 2 |

## Quantum layer (WS1)

| ID | Item | Prio | Wk |
|---|---|---|---|
| Q1 | BB84 model: random bits/bases, loss, depolarizing error rate | M | 2 |
| Q2 | Sifting over `AuthenticatedChannel` | M | 2 |
| Q3 | QBER estimation (sample + discard) and abort threshold (~11%) | M | 2 |
| Q4 | Error correction: simplified Cascade, counting leaked bits | M | 3 |
| Q5 | Privacy amplification with Toeplitz hashing; secret key length formula | M | 3 |
| Q6 | Intercept-resend Eve; check that QBER rises to ~25% | S | 3 |
| Q7 | Fallback: error correction via leakage formula only (if Q4 slips) | S | 3 |
| Q8 | Decoy-state / finite-key effects | W | – |

## KMS + channel (WS2)

| ID | Item | Prio | Wk |
|---|---|---|---|
| K1 | `KeyStore` in memory, per-peer key pools, key IDs | M | 2 |
| K2 | ETSI-014 subset REST API (FastAPI) | S | 3 |
| K3 | Transport: in-process queue + latency model (RTT parameter) | M | 2 |
| K4 | End-to-end wiring: N nodes, links, KMS per node | M | 3–4 |
| K5 | Trusted-node relay for non-adjacent nodes | C | 5 |

## Auth A: PSK + Wegman–Carter (WS3)

| ID | Item | Prio | Wk |
|---|---|---|---|
| A1 | Universal hash (polynomial over GF(2¹²⁸) or Toeplitz) + OTP tag | M | 2 |
| A2 | Pairwise PSK provisioning for n nodes; storage accounting | M | 2 |
| A3 | Key-pool consumption and refill from QKD output via `KeyStore` | M | 3 |
| A4 | Failure mode: pool exhausted → re-provisioning required | S | 3 |
| A5 | Help WS5 with the analytic PSK scaling model | S | 4 |

## Auth B: Kerberos-lite (WS4)

| ID | Item | Prio | Wk |
|---|---|---|---|
| B1 | KDC database: node → long-term key (AES-256) | M | 2 |
| B2 | AS exchange: TGT + session key | M | 2 |
| B3 | TGS exchange: service ticket for the peer with K_AB | M | 3 |
| B4 | AP exchange: ticket + authenticator, mutual authentication | M | 3 |
| B5 | Replay cache, timestamps, ticket lifetime | M | 3 |
| B6 | `Session.tag/verify` = HMAC-SHA256 / AES-GMAC with a subkey from K_AB | M | 3 |
| B7 | Ticket caching; measure first-contact vs. repeat-contact cost | S | 4 |
| B8 | KDC load simulation (many concurrent clients) | S | 4 |
| B9 | Long-term key refill from a QKD link to the KDC | C | 5 |
| B10 | Swap in real MIT Kerberos (Docker KDC) behind the same interface | C | 5 |

## Auth C: PQC (stretch goal, any WS with spare capacity)

| ID | Item | Prio | Wk |
|---|---|---|---|
| P1 | ML-DSA signature authenticator via `liboqs-python` | C | 5 |
| P2 | Minimal CA / certificate distribution for onboarding | C | 5 |
| P3 | Hybrid: PQC for first contact, then PSK from QKD output | W | – |

## Benchmarks + scaling (WS5)

| ID | Item | Prio | Wk |
|---|---|---|---|
| M1 | `MetricsSink` JSONL + loader into pandas | M | 1 |
| M2 | Scenario runner: variant × n_nodes × RTT × QBER, seeded | M | 3 |
| M3 | Analytic scaling model: storage, onboarding, key consumption, KDC load | M | 3 |
| M4 | Many-node simulation (n up to 1000) that only counts, without quantum sim | M | 4 |
| M5 | Plots for every metric in PLAN.md §6 | M | 5 |
| M6 | Statistical rigour: repeats, confidence intervals | S | 5 |

## Threat analysis (WS6)

| ID | Item | Prio | Wk |
|---|---|---|---|
| T1 | System model: assets, actors, trust boundaries, data-flow diagram | M | 1 |
| T2 | Attacker models: passive, active MITM, quantum-capable, insider/KDC compromise | M | 2 |
| T3 | STRIDE per component for variant A and B | M | 4 |
| T4 | Attack trees: "learn the final key", "impersonate a node", "deny service" | M | 5 |
| T5 | Security-level comparison: information-theoretic (A) vs. computational + trusted KDC (B); harvest-now-decrypt-later; PKINIT is not quantum-safe | M | 5 |
| T6 | Practical tests on the prototype: replay, ticket tampering, Eve detection | S | 5 |
| T7 | Tamarin/ProVerif model of Kerberos-lite authenticating QKD post-processing | C | 5 |

## Report (WS6 leads, everyone writes)

| ID | Item | Prio | Wk |
|---|---|---|---|
| R1 | Report outline + ownership of each section | M | 2 |
| R2 | Each WS writes its own section | M | 5 |
| R3 | Results + discussion + conclusion | M | 6 |
| R4 | Presentation | M | 6 |
