FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="08f36a1838d2d65f09a2b93f21dc83dbe663df3ff8da8095bd05e20d7b09b3d8"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
RUN chmod +x /tests/test.sh
