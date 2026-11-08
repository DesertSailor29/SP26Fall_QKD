# SP26Fall_QKD

Semester project (Masters, 1st semester, Fall 2026) on **quantum key distribution (QKD)**.

## What this project is about

QKD lets two parties grow a shared secret key whose security rests on physics rather than on
computational assumptions. It only works if the **classical channel** used for post-processing
(basis sifting, error correction, privacy amplification) is authenticated. The textbook solution is
pre-shared keys with Wegman–Carter authentication, which is information-theoretically secure but
needs n(n−1)/2 pairwise keys for n users and uses up key material on every message.

We test whether **Kerberos** can replace those pairwise pre-shared keys: n long-term keys held by one
Key Distribution Center instead of roughly n² pairwise keys. We then measure what this gains (speed,
storage, scaling) and analyse what it costs in security (a trusted KDC, and only computational security).

## Planned deliverables

1. A working prototype with swappable authentication of the classical channel:
   - **A)** pre-shared keys + Wegman–Carter
   - **B)** Kerberos-lite
2. Measurements comparing A and B, plus a scaling model for large numbers of nodes.
3. A structured threat analysis (STRIDE + attack trees).
4. A report and a presentation.

Stretch goals: **C)** post-quantum signature authentication, real MIT Kerberos, and a formal protocol
model in Tamarin/ProVerif.

## Architecture (planned)

```
Benchmark harness: scenarios, metrics, scaling model, plots
Auth layer (swappable): A) PSK+Wegman–Carter | B) Kerberos-lite | C) PQC
Classical channel: message transport + simulated latency
KMS: ETSI GS QKD 014-style key store and API
Quantum layer: BB84 model -> sifting -> error correction -> privacy amplification
```

The quantum layer is a model of BB84 (configurable error rate, loss and an optional eavesdropper),
not a physical simulation.

## Team

Group of 6 students; deadline early December 2026.
