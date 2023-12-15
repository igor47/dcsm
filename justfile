build:
  docker build . -t dcsm:latest

keygen:
  docker compose run --build --rm dcsm keygen

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
  # type tests
  mypy .
  # run unit tests
  python test.py
  # now run e2e test
  docker compose up --build --remove-orphans --force-recreate
