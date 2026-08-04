# Exact rational matrix determinants

`matrix.determinant.compute` computes one exact determinant for a square matrix
over `QQ`. `matrix.determinant.verify` independently recomputes and checks one
stored result. Computation and verification are separate trust boundaries.

## Input and result contracts

The matrix artifact contains a nonempty square matrix with at most 32 rows and
columns. Every entry is a canonical reduced rational:

```json
{"num": "-3", "den": "7"}
```

`matrix.determinant.compute` uses SymPy's exact matrix determinant API with the
fraction-free Bareiss method. It stores:

- the canonical source matrix;
- one determinant artifact whose payload identifies that matrix;
- exact source-parent lineage; and
- the SymPy backend version and method.

The compute result remains `COMPUTED` and `UNVERIFIED`. Backend success is an
execution result, not independent assurance. SymPy documents both the
[`Matrix.det` API][sympy-det] and its Bareiss method.

## Independent verification

With bundled references enabled, `matrix.determinant.verify` runs an
operator-authorized standard-library checker in a clean process. The verifier
accepts only when all of the following hold:

1. claim, candidate, and witness schemas, semantics, payload digests, and
   parent lineage agree;
2. the candidate and witness identify the exact stored source matrix and
   determinant artifact;
3. all rational values are canonical, reduced, and have positive
   denominators; and
4. exact Gaussian elimination over `fractions.Fraction`, including row-swap
   signs, recomputes the declared determinant.

The checker does not import SymPy or producer code. Accepted replay creates a
verification record and may report `VERIFIED`. A wrong value, malformed
binding, timeout, cancellation, or checker error reports `UNKNOWN` and creates
no verification record.

Verification covers only the equality

```text
declared value = det(stored source matrix)
```

It does not separately conclude invertibility, rank, orientation, volume, or
any downstream theorem. An agent can compose those later from the verified
artifact.

## Public reproduction

The integration reproduction uses

```text
[[1, 0, 1],
 [2, -1, 3],
 [4, 3, 2]]
```

The producer stores determinant `-1`; the independent checker recomputes the
same exact value and emits a bound verification record. Attack cases mutate
the value while refreshing its payload digest, rebind the source URI, supply
noncanonical rationals, add unexpected fields, and force a checker timeout.

[sympy-det]: https://docs.sympy.org/latest/modules/matrices/matrices.html#sympy.matrices.matrixbase.MatrixBase.det
