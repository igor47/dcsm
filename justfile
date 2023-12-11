build:
  docker build . -t dcsn:latest

encrypt:
  docker compose run --build --rm dcsm encrypt

decrypt:
  docker compose run --build --rm dcsm decrypt

run:
  docker compose run --build --rm dcsm

test:
  #!/usr/bin/env bash
  set -euo pipefail
  # remove dangling result from previous test
  rm -rf example/templates/test
  # now run the test
  docker compose up --build --remove-orphans --force-recreate
