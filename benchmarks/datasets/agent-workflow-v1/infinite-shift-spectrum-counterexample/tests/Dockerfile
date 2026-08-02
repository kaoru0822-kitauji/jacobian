FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for an infinite-shift eigenvalue-set scope audit.
LABEL jacobian.task="jacobian/infinite-shift-spectrum-counterexample" \
      jacobian.checksum="bdffee232b38d048a0a21ae5828e732f1124bd16a135c35dc8c8ebeb383c04f0"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/infinite-shift-spectrum-counterexample"'
