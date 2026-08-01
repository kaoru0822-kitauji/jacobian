FROM ghcr.io/astral-sh/uv:0.8.4-python3.12-bookworm-slim@sha256:dc7e1d08f8ca979826ec0b68b31c783e0b35b568be6a078d4cbedf38c4cc085e
# Build context key: polynomial normalization.
LABEL jacobian.task="jacobian/polynomial-normalization" \
      jacobian.checksum="3e1fa6d9c35b21860f6a539c316bb6ec8a4f73de7b4d0997ccd2f10223dabbad"
COPY authorized_record.json agent-workflow-v1-polynomial-normalization-expected.json agent-workflow-v1-polynomial-normalization-input.json test.sh verifier.py verifier_support.py /tests/
COPY agent-workflow-v1-polynomial-normalization-input.json /app/input.json
RUN chmod +x /tests/test.sh && \
    python -c 'import json; assert json.load(open("/tests/agent-workflow-v1-polynomial-normalization-expected.json"))["task_id"] == "jacobian/polynomial-normalization"'
