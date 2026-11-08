# Simplifications

Every simplification in the simulation is listed here, along with the phase that removes it (if any).
Phases follow the BB84 roadmap: 1 core, 2 authentication, 3 QBER, 4 noise, 5 Eve, 6 error correction,
7 privacy amplification, 8 key confirmation, 9 separate processes.

| # | Simplification | Why it is acceptable | Removed in |
|---|---|---|---|
| 1 | The quantum channel is a model, not a quantum-state simulation. Measuring in the matching basis returns the prepared bit; measuring in the other basis returns a fair coin flip. | These are exactly the BB84 measurement statistics for ideal single photons. | Never (Qiskit could become an optional backend) |
| 2 | No security comes from physics. Eve's measurement will be a function call. | The project studies protocol and authentication behaviour, not physical security. | Never |
| 3 | Ideal single-photon source and detectors: no loss, no multi-photon pulses, no dark counts. | Phase 1 only checks that the protocol logic is correct. | Loss is a later option; decoy states are out of scope |
| 4 | Perfect channel: no noise, no eavesdropper. | Phase 1 only checks that the protocol logic is correct. | 4 (noise), 5 (Eve) |
| 5 | The classical channel is unauthenticated. | Phase 1 only checks that the protocol logic is correct. | 2 |
| 6 | All pulses are sent and measured as one batch before sifting starts. | It matches a fixed-block-size protocol and keeps the code simple. | Never in v1 |
| 7 | Single process, in-memory transport, and the runner moves pulses from Alice to the channel to Bob. | Parties still share no state: classical messages are serialized to bytes and pulse arrays are copied. | 9 (TCP) |
| 8 | Bob announces his bases and Alice replies with the match mask. Alice never reveals her bases directly. | This is a standard sifting variant; Eve learns the same matched positions either way. | Never |
