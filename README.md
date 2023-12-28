# Docker Compose Secrets Manager

Target audience:
* You run your self-hosted infrastructure using `docker-compose.yaml` files
* You keep your infra checked into a git repo, [configuration-as-code/infrastructure-as-code](https://www.cloudbees.com/blog/configuration-as-code-everything-need-know) style

You probably have the question -- <b>what the heck do you do with the secrets?</b>

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

Here, we bind-mount the entire git repo to `/config` inside the container.
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


## Environment Variables

The following environment variables are required by `dcsm` and MUST be specified:

* `DCSM_KEYFILE` -- path to the private key file inside the container
* `DCSM_SECRETS_FILE` -- path to the encrypted secrets file inside the container

The keyfile in `DCSM_KEYFILE` **must not** be checked into your git repo.
It can be created locally if you have [age](https://age-encryption.org/) installed (see the [Example section](#Example) for a full walk-through).
Alternatively, you can have `dcsm` generate it:

```
$ docker compose run --rm dcsm keygen
successfully generated key file /secrets/key.private
```

Additionally, you SHOULD specify any number of environment variables beginning with `DCSM_TEMPLATE_` (e.g., `DCSM_TEMPLATE_CONFIGS`).
These should point to directories inside the container.
In those directories, `dcsm` will find `*.template` files and process them, replacing `$DCSM{VAR}` with the value of the secret `VAR`.

You MAY optionally specify a `DCSM_SOURCE_FILE` environment variable.
The file in `DCSM_SOURCE_FILE` **must not** be checked into your git repo.
Specifying it will allow you to invoke `dcsm` with the `encrypt`/`decrypt` commands to help you manage your plaintext/encrypted secrets files:

```
$ docker compose run --rm dcsm encrypt
successfully encrypted source file /secrets/secrets.yaml => /secrets/secrets.encrypted
$ docker compose run --rm dcsm decrypt
successfully decrypted secrets file /secrets/secrets.encrypted -> /secrets/secrets.yaml
don't forget to re-encrypt and remove the source file!
```

## Templates

Files with the  `.template` extension in all `DCSM_TEMPLATE_X` directories will be processed by `dcsm`.
The template files can be of any format (e.g., `config.yaml.template`, `config.ini.template`, etc...).
For every file ending with `.template`, `dcsm` will create a file with `.template` removed, with the same ownership and permissions.

Inside `.template` files, use your secret vars like so: `$DCSM{secret}`.
Here, that string will be replaced with the value of the secret `secret` found in your `secrets.encrypted` file.

### Templating `env_file`s

If your service requires secrets provided as environment variables, you may template `env_file` files.
For example, if you want a secret password for a [postgres container](https://hub.docker.com/_/postgres/), create a `postgres.env.template` file:

```bash
POSTGRES_PASSWORD=$DCSM{POSTGRES_PASSWORD}
```

And provide it to your container like so:

```yaml
postgres:
  image: postgres
  depends_on:
    dcsm:
      condition: service_completed_successfully
  env_file:
    - postgres.env
```

`dcsm` will copy `postgres.env.template` to `postgres.env`, replacing `$DCSM{POSTGRES_PASSWORD}` with the value of the secret in your `secrets.encrypted` file.

### Missing Files

When you depend on `dcsm`, your `compose.yaml` file ends up specifying files that don't (yet) exist.
For example, if you specify `postgres` as in the example above, then `docker compose` will complain:

```
Failed to load postgres.env: open postgres.env: no such file or directory
```

This is because your repo contains `postgres.env.template` -- `postgres.env` will not exist until after `dcsm` runs.
You can create all the missing files by running `dcsm`:

```
$ docker compose up dcsm
[+] Running 1/0
 ✔ Container dcsm-1  Created                                                                                                            0.0s
Attaching to dcsm-1
dcsm-1  | successfully processed 1 template files
```

Unfortunately, `docker compose` will complain about the missing files, even if they do not pertain to the service you `up`.
There are two hacky workarounds (sorry about this!):

1. temporarily edit your `compose.yaml` to remove all services except `dcsm`, then `docker compose dcsm up`
1. create fake versions of the missing files (e.g. `touch postgres.env`)

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

Most dev tasks are documented in code in the `Justfile`.
Install [`just`](https://just.systems/man/en/chapter_4.html) and run `just` to see the available tasks.

### Requirements

Prod requirements are stored in `requirements.txt`.
Additional dev mode requirements are in `requirements-dev.txt`.
Use `pip sync requirements.txt` to put your environment into prod mode.
