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

    def check_set(self, keyfile: bool = False, secrets: bool = False, source: bool = False) -> None:
        """Check that the given file is set"""
        if keyfile and not self.keyfile:
            raise ValueError("variable DCSM_KEYFILE is required")
        if secrets and not self.secrets:
            raise ValueError("variable DCSM_SECRETS_FILE is required")
        if source and not self.source:
            raise ValueError("variable DCSM_SOURCE_FILE is required")

    def check_exists(self, keyfile: bool = False, secrets: bool = False, source: bool = False) -> None:
        """Check that the given file exists"""
        self.check_set(keyfile, secrets, source)
        assert self.keyfile and self.secrets and self.source

        if keyfile and not self.keyfile.exists:
            raise ValueError(f'DCSM_KEYFILE {self.keyfile} does not exist')
        if secrets and not self.secrets.exists:
            raise ValueError(f'DCSM_SECRETS_FILE {self.secrets} does not exist')
        if source and not self.source.exists:
            raise ValueError(f'DCSM_SOURCE_FILE {self.source} does not exist')

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
    files.check_exists(keyfile=True, secrets=True)
    assert files.keyfile and files.secrets

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
    files.check_set(secrets=True)
    files.check_exists(keyfile=True, source=True)
    assert files.keyfile and files.secrets and files.source

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
    files.check_set(source=True)
    files.check_exists(keyfile=True, secrets=True)
    assert files.keyfile and files.secrets and files.source

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

def keygen(files: Files) -> None:
    """Generate a key file"""
    files.check_set(keyfile=True)
    assert files.keyfile

    if files.keyfile.exists:
        raise ValueError(f'key file {files.keyfile} already exists')

    process = subprocess.run(
        ['age-keygen', '--output', files.keyfile.path],
        env={},
        capture_output=True,
    )
    if process.returncode != 0:
        raise ValueError(f'age-keygen failed: {process.stderr.decode("utf-8")}')

    print(f"successfully generated key file {files.keyfile.path}")

def main() -> None:
    """DCSM entry point"""
    usage = "Usage: dcsm <run|encrypt|decrypt|keygen>"
    try:
        task = sys.argv[1]
    except IndexError:
        print(usage)
        sys.exit(1)

    # we always need the keyfile no matter what we're doing
    files = Files()
    if task == "run":
        run(files)
    elif task == "keygen":
        keygen(files)
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
