"""Read-only GD13MY package, ROM checksum and export audit."""

from configparser import ConfigParser
from hashlib import md5, sha256
import json
from pathlib import Path
import zlib

from build_ce_minimal import API
from extract_spd import read_members
from inspect_ce import inspect_rom
from inspect_ce_pe import rom_exports
from inspect_firmware import ROOT, pe
from phase1_rom import module_details


def audit(source):
    version = (source / 'i30_2013.ver').read_text(encoding='ascii').splitlines()
    identity = version[0].split('|')
    if identity[2:5] != ['GD13MY.KOR.SOP.00.061', 'HM', 'i30_2013']:
        raise ValueError('Unexpected GD13MY package identity')
    stock = source / 'GD13MY'
    checks = 0
    for line in version[1:]:
        folder, name, _, crc, size, _ = line.split('|')
        relative = folder.removeprefix('i30_2013').replace('\\', '/').strip('/')
        if relative not in ('', 'GD13MY'):
            continue
        path = (source / relative / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError('Manifest entry leaves the stock package directory')
        data = path.read_bytes()
        if len(data) != int(size) or zlib.crc32(data) != (int(crc) & 0xffffffff):
            raise ValueError(f'Manifest checksum mismatch for {name}')
        checks += 1

    components = {}
    kernel = None
    for role in ('APP', 'BSP', 'MICOM', 'ACC'):
        files = chunks = 0
        for _, _, content, entry, records in read_members((stock / f'{role}.hdr').read_bytes(),
                                                          (stock / f'{role}.spd.000').read_bytes()):
            files += 1
            chunks += len(records)
            if role == 'BSP' and entry['name'] == 'kernel':
                kernel = content
        components[role] = {'files': files, 'zlib_members': chunks}

    if kernel is None:
        raise ValueError('BSP kernel is missing')
    rom, read = inspect_rom(kernel, include_reader=True)
    coredll = next(row for row in rom.pop('contents') if row['kind'] == 'module' and row['name'].lower() == 'coredll.dll')
    live = {item['name']: item['ordinal'] for item in module_details(coredll, read)['exports'] if item['name']}
    previously_seen = rom_exports()
    if {name: live[name] for name in API} != {name: previously_seen[name] for name in API}:
        raise ValueError('Current stock exports differ from the CE build evidence')

    updater = (source / 'install.exe').read_bytes()
    if md5(updater).digest() != (source / 'install.md5').read_bytes():
        raise ValueError('Installer digest differs from install.md5')
    programs = {}
    for name, data in (('install.exe', updater), ('AVNRecovery.exe', (source / 'AVNRecovery.exe').read_bytes())):
        header = pe(data)
        programs[name] = {'sha256': sha256(data).hexdigest(), 'machine': header['machine'],
                          'pe_security_directory': header['security_directory']}
    config = ConfigParser(interpolation=None)
    config.read_string((stock / 'install.ini').read_bytes().decode('utf-8-sig'))
    return {'version': identity[2], 'manifest_crc32_entries_rechecked': checks, 'components': components,
            'installer_md5_match': True, 'installer_pe': programs, 'kernel_sha256': sha256(kernel).hexdigest(),
            'rom': rom, 'probe_ordinals_matched': {name: live[name] for name in API},
            'install_flags': {role: config[role].getboolean('install')
                              for role in ('bsp', 'app', 'acc', 'map', 'micom', 'bluetooth')},
            'partitioning': config['option'].getint('partitioning')}


if __name__ == '__main__':
    print(json.dumps(audit(Path(ROOT / 'firmware/original')), indent=2))
