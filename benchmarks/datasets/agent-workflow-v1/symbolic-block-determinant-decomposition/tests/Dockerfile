FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL jacobian.checksum="e8460adb85ac1bf46aff0605e9db7047bab7e5ef2370a7152a45ea050b7c5e57"
LABEL jacobian.task="jacobian/symbolic-block-determinant-decomposition"
COPY expected.json input.json test.sh verifier.py verifier_support.py /tests/
COPY input.json /app/input.json
RUN chmod +x /tests/test.sh
