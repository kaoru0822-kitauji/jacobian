FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for an infinite-shift eigenvalue-set scope audit.
LABEL jacobian.task="jacobian/infinite-shift-spectrum-counterexample" \
      jacobian.checksum="f131c18fe7f289f7ca530ccc9e51ef6409878cc3ad115807a123b0e80a578b54"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/infinite-shift-spectrum-counterexample"'
