build:
  docker build . -t dcsn:latest

encrypt:
  age --encrypt --armor --identity example/key.private --output example/secrets.encrypted example/secrets.yaml

test-decrypt:
  #!/usr/bin/env bash
  set -euo pipefail
  export DCSM_KEYFILE=example/key.private
  export DCSM_SECRET_FILE=example/secrets.encrypted
  export DCSM_TEMPLATE_DIR1=example/templates
  python3 ./dcsn.py decrypt

docker-decrypt: build
  docker run --rm --env DCSM_KEYFILE=/run/secrets/key.private --env DCSM_SECRET_FILE=/run/secrets/secrets.encrypted --env DCSM_TEMPLATE_DIR1=/run/secrets/templates --volume ${PWD}/example:/run/secrets dcsn:latest

docker-e2e:
  #!/usr/bin/env bash
  set -euo pipefail
  cd e2e
  #
  # remove any dangling files from previous test
  rm -rf templates/test secrets
  #
  # make a secrets directory with key and encrypted secrets file
  mkdir -p secrets
  age-keygen -o secrets/key.private
  echo 'TEST: "expected string"' > secrets/secrets.yaml
  age --encrypt --armor --identity secrets/key.private --output secrets/secrets.encrypted secrets/secrets.yaml
  rm secrets/secrets.yaml
  #
  # now run the test
  docker compose up
