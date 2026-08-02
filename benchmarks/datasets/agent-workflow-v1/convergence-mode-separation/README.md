# Convergence-mode separation

This Assurance benchmark is derived from formal-conjectures issue #3473 and the pinned `ErdosProblems/522.lean` blob `442b79dd1c1151740d9ce17551c1c9c9d77f5987`.

It asks for a replayable typewriter-sequence certificate separating convergence in probability from almost-sure convergence. The verifier derives dyadic block sizes, probabilities, and probe hit indices using exact rational arithmetic. It does not rely on frozen answer labels.

Difficulty is **Hard (provisional)** because the task combines probability semantics, an infinite block construction, quantitative convergence, and pointwise nonconvergence. No baseline calibration has yet been run. It audits the distinction between convergence modes and does not adjudicate Erdős problem 522.

