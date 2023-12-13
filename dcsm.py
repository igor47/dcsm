import datetime
import os
import os.path
import string
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
import re

import yaml

@dataclass
class FileInfo:
    """Info about a specific file we use here"""
    path: Path
    modified: Optional[datetime.datetime] = None

    @classmethod
    def from_env(cls, var: str) -> Optional['FileInfo']:
        """Loads file info from given enviroment variable"""
        name = os.environ.get(var)
        if not name:
            return None

        file = cls(path=Path(name).resolve())
        if file.exists:
            file.modified = datetime.datetime.fromtimestamp(
                file.path.stat().st_mtime
            )

        return file

    @property
    def exists(self) -> bool:
        """Does this file exist?"""
        return self.path.is_file()

    def __str__(self) -> str:
        return str(self.path)

@dataclass
class Files:
    """Info about all of our necessary files"""
    keyfile: Optional[FileInfo] = field(
        default_factory=lambda: FileInfo.from_env('DCSM_KEYFILE'))
    secrets: Optional[FileInfo] = field(
        default_factory=lambda: FileInfo.from_env('DCSM_SECRETS_FILE'))
    source: Optional[FileInfo] = field(
        default_factory=lambda: FileInfo.from_env('DCSM_SOURCE_FILE'))

class DCSMTemplate(string.Template):
    delimiter = '$DCSM'
    flags = re.RegexFlag(value=0)

    pattern = r"""
        (?P<escaped>\$\$DCSM) |
        (?:\$DCSM_(?P<named>[A-Z][A-Z0-9_]*)) |
        (?:\$DCSM\{(?P<braced>[a-zA-Z][a-zA-Z0-9_]*)\}) |
        (?P<invalid>$DCSM(?:\{\})?)
    """ # type: ignore

def get_secrets(files: Files) -> Dict[str, Any]:
    """Return the secrets as a dictionary"""
    assert files.keyfile

    if not files.secrets:
        raise ValueError("variable DCSM_SECRETS_FILE is required")
    if not files.secrets.exists:
        raise ValueError(f'DCSM_SECRETS_FILE {files.secrets} does not exist')

    process = subprocess.run(
        ['age', '--decrypt', '--identity', files.keyfile.path, files.secrets.path],
        env={},
        capture_output=True,
    )
    if process.returncode != 0:
        raise ValueError(f'age decryption failed: {process.stderr.decode("utf-8")}')

    output = process.stdout.decode('utf-8')
    secrets: Dict[str, Any] = yaml.safe_load(output)

    for key, value in secrets.items():
        if not isinstance(key, str):
            raise ValueError(f'secret key {key} is not a string')

    return secrets

def process_template(source: Path, secrets: Dict[str, Any]) -> None:
    """Process a template file, inserting secrets"""
    dest = source.with_suffix('')
    with source.open() as template:
        try:
            result = DCSMTemplate(template.read()).substitute(secrets)
        except Exception as e:
            raise ValueError(f'error processing {source}: {e}')

        with dest.open('w') as output:
            output.write(result)

        # copy ownership and permissions from source to dest
        stat = source.stat()
        os.chown(dest, stat.st_uid, stat.st_gid)
        os.chmod(dest, stat.st_mode)

def process_dir(dirname: str, secrets: Dict[str, Any]) -> int:
    """Process all template files in the directory"""
    processed = 0
    for root, dirs, files in os.walk(dirname):
        dir = Path(root).absolute()
        for filename in files:
            if filename.endswith('.template'):
                process_template(dir.joinpath(filename), secrets)
                processed += 1

    return processed

def encrypt(files: Files) -> None:
    """Encrypt the source file into the secrets file"""
    assert files.keyfile

    if not files.secrets:
        raise ValueError("variable DCSM_SECRETS_FILE is required")

    if not files.source:
        raise ValueError("variable DCSM_SOURCE_FILE is required")
    if not files.source.exists:
        raise ValueError(f'DCSM_SOURCE_FILE {files.source} does not exist')

    source_is_newer = False
    if not files.secrets.exists:
        source_is_newer = True
    elif files.source.modified and files.secrets.modified:
        source_is_newer = files.source.modified > files.secrets.modified

    if not source_is_newer:
        raise ValueError('encrypted secrets are newer than secrets source; will not overwrite')

    process = subprocess.run(
        ['age', '--encrypt', '--identity', files.keyfile.path, '--output', files.secrets.path, files.source.path],
        env={},
        capture_output=True,
    )
    if process.returncode != 0:
        raise ValueError(f'age encryption failed: {process.stderr.decode("utf-8")}')

    print(f"successfully encrypted source file {files.source.path} => {files.secrets.path}")

def decrypt(files: Files) -> None:
    """Decrypt the secrets file back out to the source file"""
    assert files.keyfile

    if not files.source:
        raise ValueError("variable DCSM_SOURCE_FILE is required")

    if not files.secrets:
        raise ValueError("variable DCSM_SECRETS_FILE is required")
    if not files.secrets.exists:
        raise ValueError(f'DCSM_SECRETS_FILE {files.source} does not exist')

    secrets_newer = False
    if not files.source.exists:
        secrets_newer = True
    elif files.source.modified and files.secrets.modified:
        secrets_newer = files.secrets.modified > files.source.modified

    if not secrets_newer:
        raise ValueError('secret source file is newer than encrypted secrets file; will not overwrite')

    process = subprocess.run(
        ['age', '--decrypt', '--identity', files.keyfile.path, '--output', files.source.path, files.secrets.path],
        env={},
        capture_output=True,
    )
    if process.returncode != 0:
        raise ValueError(f'age decryption failed: {process.stderr.decode("utf-8")}')

    print(f"successfully decrypted secrets file {files.secrets.path} -> {files.source.path}")
    print("don't forget to re-encrypt and remove the source file!")

def run(files: Files) -> None:
    """Process all template files"""
    secrets = get_secrets(files)

    processed = 0
    for key, dirname in os.environ.items():
        if not key.startswith('DCSM_TEMPLATE_'):
            continue

        if not os.path.exists(dirname):
            raise ValueError(f'DCSM_TEMPLATE_{key} {dirname} does not exist')

        processed += process_dir(dirname, secrets)

    print(f"successfully processed {processed} template files")

def main() -> None:
    """DCSM entry point"""
    usage = "Usage: dcsm <run|encrypt|decrypt>"
    try:
        task = sys.argv[1]
    except IndexError:
        print(usage)
        sys.exit(1)

    # we always need the keyfile no matter what we're doing
    files = Files()
    if not files.keyfile:
        raise ValueError("variable DCSM_KEYFILE is required")
    if not files.keyfile.exists:
        raise ValueError(f'DCSM_KEYFILE {files.keyfile} does not exist')

    if task == "run":
        run(files)
    elif task == "encrypt":
        encrypt(files)
    elif task == "decrypt":
        decrypt(files)
    else:
        print(usage)
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Unexpected error: {}".format(e))
        sys.exit(1)
    else:
        sys.exit(0)
