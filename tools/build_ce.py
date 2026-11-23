"""Build the native bench probe and adapter library with a CE 6 ARMV4I SDK."""

import argparse
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from inspect_firmware import ROOT, pe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool-bin', required=True, type=Path, help='Legacy ARMV4I cl.exe and link.exe directory')
    parser.add_argument('--sdk-include', required=True, type=Path, help='OEM CE 6 SDK include directory')
    parser.add_argument('--sdk-lib', required=True, type=Path, help='OEM CE 6 SDK ARMV4I library directory')
    args = parser.parse_args()
    cc, linker = (args.tool_bin.resolve() / f'{name}.exe' for name in ('cl', 'link'))
    includes = args.sdk_include.resolve()
    libraries = [args.sdk_lib.resolve() / name for name in ('coredll.lib', 'corelibc.lib')]
    for path in (cc, linker, includes / 'windows.h', *libraries):
        if not path.is_file():
            parser.error(f'Required ARMV4I SDK input is missing: {path}')

    def run(*command):
        subprocess.run(command, cwd=staging, check=True)

    with TemporaryDirectory(prefix='i30-ce-') as temporary:
        staging = Path(temporary)
        for name in ('ce_wave', 'ce_supervisor', 'ce_probe'):
            run(cc, '/nologo', '/c', '/W4', '/O1', '/GS-', '/QRarch4T', '/QRinterwork-return',
                '/D_WIN32_WCE=0x600', '/DUNDER_CE=600', '/DARMV4I', '/DARM', '/D_ARM_',
                '/DUNICODE', '/D_UNICODE', f'/I{includes}', f'/Fo{name}.obj', ROOT / 'src/ce' / f'{name}.c')
        run(linker, '/lib', '/nologo', '/out:i30-ce-platform.lib', 'ce_wave.obj', 'ce_supervisor.obj')
        run(linker, '/nologo', '/machine:thumb', '/subsystem:windowsce,6.00', '/entry:WinMainCRTStartup',
            '/nodefaultlib', '/out:i30-ce-probe.exe', 'ce_probe.obj', 'i30-ce-platform.lib', *libraries)
        probe = staging / 'i30-ce-probe.exe'
        header = pe(probe.read_bytes())
        if (not header or header['machine'] != '0x1c2' or header['optional_magic'] != '0x10b'
                or header['subsystem'] != 9 or header['subsystem_version'] != (6, 0)):
            raise SystemExit('Probe failed GD13MY Windows CE ARM/Thumb PE validation')
        output = ROOT / 'build/ce'
        output.mkdir(parents=True, exist_ok=True)
        for path in (probe, staging / 'i30-ce-platform.lib'):
            shutil.copyfile(path, output / path.name)
    print(output)


if __name__ == '__main__':
    main()
