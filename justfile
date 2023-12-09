build:
  docker build .

encrypt:
  age --encrypt --armor --identity example/key.private --output example/secrets.encrypted example/secrets.yaml

test-decrypt:
  #!/usr/bin/env bash
  set -euo pipefail
  export DCSM_KEYFILE=example/key.private
  export DCSM_SECRET_FILE=example/secrets.encrypted
  python3 ./dscn.py decrypt
