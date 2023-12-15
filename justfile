
# list the available recipes
list:
  just --list --justfile {{justfile()}}

# build docker container
build:
  docker build . -t dcsm:latest

# generate age symmetric key
keygen:
  docker compose run --build --rm dcsm keygen

# encrypt secrets file
encrypt:
  docker compose run --build --rm dcsm encrypt

# decrypt secrets file
decrypt:
  docker compose run --build --rm dcsm decrypt

# run DCSM, templating all the `.template` files with secrets
run:
  docker compose run --build --rm dcsm

# run unit and an end-to-end test
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
