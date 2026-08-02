# jacobian/graph-atlas-enumeration

Enumerate a finite family of seven-vertex graph isomorphism classes.

The instruction is agent-agnostic and names no tool or capability. The hidden
clean-room verifier checks graph constraints and computes canonical labels by
replaying all vertex permutations. It compares the resulting label set with a
frozen expected set, so reordered or relabelled representatives are accepted.

This case is evaluator-labelled `HIGH` tool opportunity because complete
manual enumeration is substantially more error-prone than producing a single
witness. The label is not mounted into the agent or verifier containers and
does not alter mathematical reward or assurance.
