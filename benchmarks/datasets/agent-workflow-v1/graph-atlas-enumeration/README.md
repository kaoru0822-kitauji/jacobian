# jacobian/graph-atlas-enumeration

Enumerate a finite family of seven-vertex graph isomorphism classes.

The instruction is agent-agnostic and names no tool or capability. The hidden
clean-room verifier independently sweeps all `2^21` labelled graphs, checks the
four graph constraints, and verifies that the relabelling orbits of the
submitted representatives are disjoint and cover every satisfying graph. It
does not trust a frozen class count or answer-label set.

This case is evaluator-labelled `HIGH` tool opportunity because complete
manual enumeration is substantially more error-prone than producing a single
witness. The label is not mounted into the agent or verifier containers and
does not alter mathematical reward or assurance.
