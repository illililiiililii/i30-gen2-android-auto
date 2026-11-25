"""Create local mutual TLS credentials for an AARE phone and GD13MY emulator."""

import argparse
from getpass import getpass
from hashlib import sha256
from pathlib import Path
import ssl
import subprocess
from tempfile import TemporaryDirectory


def create_identity(openssl, output, password):
    if output.exists():
        raise FileExistsError(output)
    if not password or '\n' in password or '\r' in password:
        raise ValueError('Enter a nonempty single-line PKCS#12 password')

    with TemporaryDirectory(dir=output.parent, prefix='.gd13my-aare-') as temporary:
        stage = Path(temporary)
        files = stage / 'identity'
        files.mkdir(mode=0o700)

        def run(*args, input=None):
            return subprocess.run([openssl, *args], cwd=stage, check=True, input=input,
                                  stdout=subprocess.PIPE, text=True).stdout

        run('req', '-new', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '365',
            '-subj', '/CN=GD13MY AARE Head Unit', '-addext', 'basicConstraints=critical,CA:FALSE',
            '-addext', 'keyUsage=critical,digitalSignature', '-addext', 'extendedKeyUsage=clientAuth',
            '-keyout', 'identity/i30-aare-client-key.pem', '-out', 'identity/i30-aare-client.pem')
        run('req', '-new', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '365',
            '-subj', '/CN=GD13MY AARE Local CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', 'ca-key.pem',
            '-out', 'identity/i30-aare-ca.pem')
        run('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=GD13MY AARE Phone',
            '-keyout', 'phone-key.pem', '-out', 'phone.csr')
        (stage / 'server.cnf').write_text('basicConstraints=critical,CA:FALSE\n'
                                          'keyUsage=critical,digitalSignature,keyEncipherment\n'
                                          'extendedKeyUsage=serverAuth\n', encoding='ascii')
        run('x509', '-req', '-in', 'phone.csr', '-CA', 'identity/i30-aare-ca.pem', '-CAkey', 'ca-key.pem',
            '-days', '365', '-sha256', '-extfile', 'server.cnf', '-out', 'phone.pem')
        run('verify', '-purpose', 'sslserver', '-CAfile', 'identity/i30-aare-ca.pem', 'phone.pem')
        run('pkcs12', '-export', '-name', 'GD13MY AARE Phone', '-in', 'phone.pem', '-inkey', 'phone-key.pem',
            '-certfile', 'identity/i30-aare-ca.pem', '-out', 'identity/GD13MY-AARE.p12', '-passout', 'stdin',
            input=password + '\n')

        def fingerprint(path):
            return sha256(ssl.PEM_cert_to_DER_cert(path.read_text(encoding='ascii'))).hexdigest()

        phone = fingerprint(stage / 'phone.pem')
        head_unit = fingerprint(files / 'i30-aare-client.pem')
        (files / 'i30-aare-peer-sha256.txt').write_text(phone, encoding='ascii')
        (files / 'head-unit-sha256.txt').write_text(head_unit + '\n', encoding='ascii')
        files.rename(output)
    return head_unit, phone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New private local directory for the generated files')
    parser.add_argument('--openssl', type=Path, required=True)
    args = parser.parse_args()
    head_unit, phone = create_identity(args.openssl.resolve(strict=True), args.output.resolve(),
                                       getpass('Password for the AARE PKCS#12 import: '))
    print(f'Head unit SHA-256 {head_unit}\nPhone SHA-256 {phone}')


if __name__ == '__main__':
    main()
