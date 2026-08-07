FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
RUN python -m pip install --no-cache-dir attrs==26.1.0 jsonschema==4.26.0 jsonschema-specifications==2025.9.1 referencing==0.37.0 rpds-py==2026.6.3 typing-extensions==4.16.0
LABEL jacobian.checksum="f904a9a66f4d86f079a44567bab5375186c1ea4e2f815b1e1a65f35b6b1c60ed"
COPY expected.json input.json test.sh verifier.py verifier_support.py public_contract.json /tests/
RUN chmod +x /tests/test.sh
