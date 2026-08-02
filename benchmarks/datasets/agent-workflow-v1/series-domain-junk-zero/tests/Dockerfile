FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Exact verifier for a series-domain fallback audit.
LABEL jacobian.task="jacobian/series-domain-junk-zero" \
      jacobian.checksum="e61050cc75e0c68a7523bb77d35d000225e2fbb321dfd8834481fcdc8a67deda"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/expected.json"))["task_id"] == "jacobian/series-domain-junk-zero"'
