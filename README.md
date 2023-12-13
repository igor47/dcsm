# Docker Compose Secrets Manager

This project is intended for folks who, like me, run their self-hosted infrastructure using `docker-compose.yaml` files.
I like to keep my `docker-compose.yaml` files in a git repo.
This way, I can work on the configs locally and deploy to my remote server.
The git repo is my [configuration-as-code/infrastructure-as-code](https://www.cloudbees.com/blog/configuration-as-code-everything-need-know) for my self-hosted infrastructure.

A common issue with such projects -- <b>what the heck do you do with the secrets?</b>

`dcsm` allows you to store your secrets, encrypted, in a file in the git repo.
When your `docker compose` starts, `dcsm` will decrypt the secrets and inject them into any `*.template` files in your repo.

## Usage

Add this service to your `docker-compose.yaml` file:

```yaml
  dcsm:
    image: ghcr.io/igor47/dcsm:latest
    environment:
      - DCSM_KEYFILE=/config/key.private
      - DCSM_SECRETS_FILE=/config/secrets.encrypted
      - DCSM_TEMPLATE_DIR=/config
    volumes:
      - .:/config
```

Here, we mount the entire directory as a volume to `/config`.
Any `*.template` files in the directory will be processed by `dcsm` and the result will be written to the same path without the `.template` suffix.
You can then mount the resulting file into your service containers.

Services that depend on secrets to be injected by `dcsm` should depend on the `dcsm` service:

```yaml
  my_service:
    image: my_image
    depends_on:
      dcsm:
        condition: service_completed_successfully
```

The `secrets.yaml.encrypted` file is a YAML file encrypted using [age](https://age-encryption.org/).
The `key.private` file is the key used to encrypt the `secrets.yaml.encrypted` file.
Create `key.private` using `age-keygen` (see the [Example section](#Example) for a full walk-through).
The `key.private` file should be kept secret and should not be checked into your git repo.

Inside `.template` files, use your secret vars like so: `$DCSM{secret}`.
Here, that string will be replaced with the value of the secret `secret` found in your `secrets.encrypted` file.

## Environment Variables

The following environment variables are required and must be specified:

* `DCSM_KEYFILE` -- path to the private key file inside the container
* `DCSM_SECRETS_FILE` -- path to the encrypted secrets file inside the container

You may optionally specify a `DCSM_SOURCE_FILE` environment variable.
This will allow you to invoke `dcsm` with the `encrypt`/`decrypt` commands to help you manage your plaintext/encrypted secrets files.

Additionally, you may specify any number of environment variables beginning with `DCSM_TEMPLATE_`.
These should point to directories inside the container.
In those directories, `dcsm` will find `*.template` files and process them, replacing `$DCSM{VAR}` with the value of the secret `VAR`.

## Example

You want to run a [synapse home server](https://matrix-org.github.io/synapse/latest/welcome_and_overview.html).
The `homeserver.yaml` file needs a bunch of credentials:
* `registration_shared_secret`
* `macaroon_secret_key`
* `form_secret`

Also, you want to use a `postgres` database with the server, so you need a postgres config section.
This section has a username and password that `synapse` will use to connect to `postgres`.
Also, you have an init script for your `postgres` container which creates the database, the user, and the correct `GRANT` statements.

### Solution

Your filesystem in your `docker-compose` repo:

```
my-docker-services
├── config
│   ├── postgres
    │   └── homeserver_init.sh.template
    └── synapse
        └── homeserver.yaml.template
├── .gitignore
├── docker-compose.yaml
├── key.private
├── secrets.yaml
└── secrets.encrypted
```

To create `key.private`:

```bash
$ age-keygen -o key.private
```

Your `secrets.yaml` file will look like so:

```yaml
SYNAPSE_POSTGRES_USER: synapse
SYNAPSE_POSTGRES_PASSWORD: password
SYNAPSE_REGISTRATION_SHARED_SECRET: secret
SYNAPSE_MACAROON_SECRET_KEY: secret2
SYNAPSE_FORM_SECRET: secret3
```

In your `.gitignore`, ignore `key.private` and `secrets.yaml`:

```gitignore
key.private
secrets.yaml
```

You will need to manually transfer the `key.private` file to where you run your service.
Keep it safe -- if you lose it, you'll loose access to your secrets.

To generate the `secrets.encrypted` file:

```bash
$ age --encrypt --armor --identity key.private --output secrets.encrypted secrets.yaml
```

Your `*.template` files will use [python's `string.Template`](https://docs.python.org/3/library/string.html#template-strings) syntax.
For example, `homeserver.yaml.template`:

```yaml

registration_shared_secret: $DCSM{SYNAPSE_REGISTRATION_SHARED_SECRET}
macaroon_secret_key: $DCSM{SYNAPSE_MACAROON_SECRET_KEY}
form_secret: $DCSM{SYNAPSE_FORM_SECRET}
database:
  name: psycopg2
  txn_limit: 10000
  args:
    user: $DCSM{SYNAPSE_POSTGRES_USER}
    password: $DCSM{SYNAPSE_POSTGRES_PASSWORD}
    database: synapse
    host: localhost
    port: 5432
```

Finally, your `docker-compose.yaml` will look like so:

```yaml
version: '3.9'
services:
  dcsm:
    image: ghcr.io/igor47/dcsm:latest
    environment:
      - DCSM_KEYFILE=/config/key.private
      - DCSM_SECRETS_FILE=/config/secrets.encrypted
      - DCSM_TEMPLATE_DIR=/config
    volumes:
      - .:/config
  postgres:
    image: docker.io/library/postgres:12-alpine
    depends_on:
      dcsm:
        condition: service_completed_successfully
    volumes:
      - config/postgres:/config
  synapse:
    image: docker.io/matrixdotorg/synapse:latest
    depends_on:
      dcsm:
        condition: service_completed_successfully
    volumes:
      - config/synapse/homeserver.yaml:/data/homeserver.yaml
```

## How to NOT manage `docker compose` secrets

### Store them as plain text in your `docker compose` repo

You might think this is okay because your services are running on private networks or are otherwise inaccessible to the public.
Well -- you never know!
You might accidentally expose your service and having credentials makes it that much easier to do nefarious things.

You also might think that this is okay because your repo is private.
I would encourage you to keep your repo public!
This enables others to learn from your work and to contribute back to you.

### Manage them out-of-band

The other main option is to create and store all your secrets outside of your `docker compose` repo.
This makes it hard to know exactly what you did to bring up the service.
At some point, so much stuff has leaked out of the `docker compose` repo that it's not worth it to have the repo at all.

## Dev

### Requirements

Prod requirements are stored in `requirements.txt`.
Additional dev mode requirements are in `requirements-dev.txt`.
Use `pip sync requirements.txt` to put your environment into prod mode.
