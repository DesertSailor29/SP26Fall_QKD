"""Protocol parameters shared by the single-process runner and the party processes."""

SAMPLE_FRACTION = 0.25  # share of the sifted key sacrificed to estimate the error rate
QBER_THRESHOLD = 0.11   # BB84 abort threshold (one-way post-processing)
