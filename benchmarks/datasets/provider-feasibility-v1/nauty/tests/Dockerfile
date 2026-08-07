FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
RUN python -m pip install --no-cache-dir attrs==26.1.0 jsonschema==4.26.0 jsonschema-specifications==2025.9.1 referencing==0.37.0 rpds-py==2026.6.3 typing-extensions==4.16.0
LABEL jacobian.checksum="3a331050935a642b86803b26a9a7e128609c09e9d8812ca98bfb2d4aad053c78"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
RUN chmod +x /tests/test.sh
