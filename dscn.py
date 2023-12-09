import os
import os.path
import subprocess
import sys
import time
from typing import Any, Dict

import yaml

def sleep() -> None:
    """Sleep forever seconds"""
    while True:
        time.sleep(1)

def get_secrets() -> Dict[str, Any]:
    """Return the secrets as a dictionary"""
    keyfile = os.environ.get('DCSM_KEYFILE')
    secret_file = os.environ.get('DCSM_SECRET_FILE')

    if not keyfile or not secret_file:
        raise ValueError("DCSM_KEYFILE and DCSM_SECRET_FILE are required")

    keyfile, secret_file = os.path.abspath(keyfile), os.path.abspath(secret_file)
    if not os.path.exists(keyfile):
        raise ValueError(f'DCSM_KEYFILE {keyfile} does not exist')
    if not os.path.exists(secret_file):
        raise ValueError(f'DCSM_SECRET_FILE {secret_file} does not exist')

    process = subprocess.run(
        ['age', '--decrypt', '--identity', keyfile, secret_file],
        env={},
        capture_output=True,
    )
    if process.returncode != 0:
        raise ValueError(f'age failed: {process.stderr.decode("utf-8")}')

    output = process.stdout.decode('utf-8')
    secrets: Dict[str, Any] = yaml.safe_load(output)

    for key, value in secrets.items():
        if not isinstance(key, str):
            raise ValueError(f'secret key {key} is not a string')

    return secrets

def run() -> None:
    """Process all template files"""
    secrets = get_secrets()
    print(secrets)

def main() -> None:
    """DSCN entry point"""
    try:
        task = sys.argv[1]
    except IndexError:
        print("Usage: dscn <sleep|decrypt>")
        sys.exit(1)

    if task == "sleep":
        try:
            sleep()
        except KeyboardInterrupt:
            print("Exiting...")
            sys.exit(0)
    elif task == "decrypt":
        run()
    else:
        print("Usage: dscn <sleep|decrypt>")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Unexpected error: {}".format(e))
        sys.exit(1)
    else:
        sys.exit(0)
