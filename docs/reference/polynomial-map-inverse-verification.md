# Polynomial-map inverse verification

`polynomial.map.inverse.verify` verifies a proposed inverse of a square sparse
polynomial map over `QQ`. It is a verification capability, not an inverse
search or synthesis operation.

The request supplies:

- a forward map whose ordered input variables equal `source_variables`;
- an inverse map whose ordered input variables equal `target_variables`;
- explicit source and target variable orders of the same dimension.

The adapter computes and stores both residual families:

1. `inverse_after_forward`, in the source-variable ring;
2. `forward_after_inverse`, in the target-variable ring.

Every residual coordinate is sent through `polynomial.identity.verify` against
zero, and the resulting checker-record URIs are bound into the residual
artifact and the aggregate certificate. The authorized aggregate checker does
not trust those records as a substitute for checking: in a clean process it
parses both source maps, recomputes both compositions using independent sparse
rational arithmetic, compares every declared residual exactly, and accepts an
inverse only if every residual in both directions is zero.

The output binds the two source-map artifacts, coefficient domain, both
variable orders, both residual families, both checker-record families, the
claim, certificate, and aggregate verification record. A nonzero residual
produces a verified `FALSE`; malformed, substituted, incomplete, or
inconsistently ordered evidence fails closed as `UNKNOWN`.

The v1 bounds and canonical term rules are inherited from
`jacobian.rational-polynomial-map`: dimensions are at most four, coefficients
are canonical reduced rationals, and monomials use the declared variable order.
The request is rejected before artifact creation when conservative composition
bounds exceed 1,024 residual terms or total degree 127; this keeps both the
producer and independent replay within the registered sparse-polynomial
contract.
Rational-map inverses and inverse-candidate synthesis are outside this
capability.
