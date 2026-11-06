"""Optional administrator password; the persistent token remains a recovery/API credential."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile

ITERATIONS = 600_000


def validate_password_record(record):
    if not isinstance(record, dict) or set(record) != {'version', 'iterations', 'salt', 'digest'}:
        raise ValueError('Invalid administrator password file')
    if record['version'] != 1 or record['iterations'] != ITERATIONS:
        raise ValueError('Unsupported administrator password format')
    for key, size in (('salt', 16), ('digest', 32)):
        value = record[key]
        if not isinstance(value, str) or len(value) != size * 2:
            raise ValueError('Invalid administrator password file')
        try:
            if len(bytes.fromhex(value)) != size:
                raise ValueError
        except ValueError:
            raise ValueError('Invalid administrator password file') from None
    return record


def password_record(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 1024:
        raise ValueError('Use a password containing 8–1024 characters')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return {'version': 1, 'iterations': ITERATIONS, 'salt': salt.hex(), 'digest': digest.hex()}


def save_password(data_dir: Path, record):
    record = validate_password_record(record)
    data_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.admin-password-', dir=data_dir)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(record, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, data_dir / 'admin-password.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_password(data_dir: Path):
    path = data_dir / 'admin-password.json'
    if not path.exists():
        return None
    with path.open() as stream:
        raw = stream.read(1025)
    if len(raw) > 1024:
        raise ValueError('Invalid administrator password file')
    try:
        record = validate_password_record(json.loads(raw))
    except (ValueError, TypeError):
        raise ValueError('Invalid administrator password file') from None
    os.chmod(path, 0o600)
    return record


def check_password(candidate, record):
    if not isinstance(candidate, str) or not 8 <= len(candidate) <= 1024:
        return False
    digest = hashlib.pbkdf2_hmac('sha256', candidate.encode(), bytes.fromhex(record['salt']), record['iterations'])
    return hmac.compare_digest(digest, bytes.fromhex(record['digest']))
