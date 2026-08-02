# Reconstruct a squarefree-class obstruction proof

A finite set `S` of positive integers has exactly 2023 ordered pairs `(x,y)`
for which `xy` is a square.  Certify that `S` contains four elements whose
pairwise products are all nonsquares.

Your certificate must identify the squarefree-kernel equivalence classes,
derive that the ordered-pair count is the sum of squared class sizes, reduce
the failure of a four-element transversal to a representation of 2023 by at
most three squares, and rule that out by a complete modulo-8 residue table.
It must then reconstruct the transversal conclusion.

Submitting four unrelated integers, quoting the source conclusion, or merely
stating `2023=7 mod 8` is insufficient.  The verifier independently enumerates
all one-, two-, and three-square residue sums and checks every reconstruction
link.  Bind `/app/evidence/answer.txt` and do not claim `VERIFIED`.
