# cddlib H/V feasibility

Builds cddlib 0.94n and pycddlib 3.0.2 from the exact frozen source archives,
runs the four bounded H/V cases, and retains the spike's standard-library
soundness replay. The provider remains a producer capped at `COMPUTED`; the
same-provider round trip does not establish completeness.
