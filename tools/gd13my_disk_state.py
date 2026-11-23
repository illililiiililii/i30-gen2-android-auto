"""Store virtual DiskA writes across emulator runs without changing either image."""

from contextlib import closing, contextmanager
from hashlib import sha256
import sqlite3
from struct import unpack_from

from gd13my_mmio import ReadOnlyHsMmc


def disk_identity(card):
    sector_size = ReadOnlyHsMmc.SECTOR
    card.image.seek(0)
    mbr = card.image.read(sector_size)
    if len(mbr) != sector_size or mbr[510:] != b'\x55\xaa' or mbr[450] != 0x0c:
        raise ValueError('Persistent state requires the GD13MY DiskA FAT32 partition')
    start, count = unpack_from('<II', mbr, 454)
    if not start or not count or card.first_lba + start + count > card.sectors:
        raise ValueError('Persistent state requires a complete DiskA partition')
    digest = sha256(mbr[446:462])
    card.image.seek(start * sector_size)
    remaining = count * sector_size
    while remaining:
        data = card.image.read(min(remaining, 4 * 1024 * 1024))
        if not data:
            raise ValueError('The DiskA image ended while computing its identity')
        digest.update(data)
        remaining -= len(data)
    first = card.first_lba + start
    return f'{first}:{count}:{digest.hexdigest()}', first, first + count


@contextmanager
def persistent_diska(path, card):
    identity, first, end = disk_identity(card)
    try:
        with closing(sqlite3.connect(path, timeout=0, isolation_level=None)) as db:
            # Hold the write reservation for the run. A second emulator cannot overwrite it.
            db.execute('BEGIN IMMEDIATE')
            tables = {name for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables:
                db.execute('CREATE TABLE disk (identity TEXT PRIMARY KEY)')
                db.execute('INSERT INTO disk VALUES (?)', (identity,))
                db.execute('CREATE TABLE sectors (lba INTEGER PRIMARY KEY, data BLOB NOT NULL)')
            elif (tables != {'disk', 'sectors'}
                  or db.execute('SELECT identity FROM disk').fetchall() != [(identity,)]):
                raise ValueError('The saved DiskA state is for a different image')
            saved = dict(db.execute('SELECT lba, data FROM sectors'))
            if any(not first <= lba < end or not isinstance(data, bytes) or len(data) != ReadOnlyHsMmc.SECTOR
                   for lba, data in saved.items()):
                raise ValueError('The saved DiskA state contains invalid sectors')
            card.overlay.update(saved)
            yield len(saved)
            changes = ((lba, data) for lba, data in card.overlay.items()
                       if first <= lba < end and saved.get(lba) != data)
            db.executemany('INSERT OR REPLACE INTO sectors VALUES (?, ?)', changes)
            db.commit()
    except sqlite3.Error as error:
        raise ValueError(f'Could not open or save DiskA state {path}: {error}') from error
