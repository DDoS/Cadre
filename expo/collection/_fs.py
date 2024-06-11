import os
import random
import logging
import sqlite3
from pathlib import Path, PurePath, PurePosixPath
from typing import Any, Callable, Generator
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from marshmallow import Schema, fields

from ._base import PhotoInfo, Collection, CollectionProcess


logger = logging.getLogger('')


cru_available = False
try:
    import sys
    sys.path.append(str(Path(__file__).absolute().parent.parent.parent / 'cru/build/release'))
    import cru
    cru_available = True
except ModuleNotFoundError:
    logger.error('cru module not found: FileSystemCollections scanning for new or modified images will not work.')


def _scan_directory_recursive(path: PurePosixPath) -> Generator[os.DirEntry, None, None]:
    with os.scandir(path) as iter:
        for entry in iter:
            if entry.is_dir(follow_symlinks=False):
                yield from _scan_directory_recursive(entry.path)
            else:
                yield entry


@dataclass
class ImageInfo:
    width: int
    height: int
    capture_date: datetime | None


def _try_load_image_info(path: PurePosixPath) -> ImageInfo | None:
    if not cru_available:
        return None

    try:
        if data := cru.load_image_info(str(path)):
            capture_date = None
            if data.times.original:
                original_time = data.times.original
                capture_date = datetime.fromtimestamp(original_time.seconds, timezone.utc)
                capture_date = capture_date.astimezone(timezone(timedelta(seconds=original_time.offset)))
            elif data.times.gps:
                capture_date = datetime.fromtimestamp(data.times.gps.seconds, timezone.utc)

            return ImageInfo(data.width, data.height, capture_date)
    except Exception as exception:
        logger.debug(f'File "{path}" is probably not an image: {exception.message}')

    return None


def _get_real_path(pure_path: PurePath | str) -> Path:
    return Path(pure_path).expanduser().resolve()


class FileSystemCollectionProcess(CollectionProcess):
    def __init__(self, id: int, identifier: str, root_path: PurePosixPath | str):
        super().__init__(id, identifier)
        self._root_path = _get_real_path(root_path)

    def update(self, db: sqlite3.Connection, cancellation_check: Callable[[], bool]):
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS fs_collections_data('
                       'photo_id INTEGER PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE, '
                       'collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE, '
                       'path TEXT NOT NULL UNIQUE, modified_date TEXT NOT NULL, scan_token TEXT NOT NULL)')

        added_count = 0
        updated_count = 0
        deleted_count = 0

        logger.info(f'Scanning {self._root_path}')
        scan_token = '%016x' % random.randrange(16**16)
        for entry in _scan_directory_recursive(self._root_path):
            if cancellation_check():
                logger.info(f'Scan was cancelled')
                break

            local_path = PurePosixPath(Path(entry.path).relative_to(self._root_path))
            modified_date = datetime.fromtimestamp(os.path.getmtime(entry.path)).astimezone()
            existing_data = db.execute('SELECT photo_id, modified_date as "d [datetime]" FROM fs_collections_data '
                                       'WHERE collection_id = ? AND path = ?', (self._id, local_path)).fetchone()

            photo_id: int = None
            if existing_data:
                photo_id, previous_modified_date = existing_data
                if previous_modified_date and modified_date <= previous_modified_date:
                    with db:
                        db.execute('UPDATE fs_collections_data SET scan_token = ? WHERE photo_id = ?', (scan_token, photo_id))
                    continue

            image_info = _try_load_image_info(entry.path)
            if not image_info:
                continue

            if photo_id is None:
                added_count += 1
            else:
                updated_count += 1

            with db:
                photos_data = {
                    'photo_id': photo_id,
                    'collection_id': self._id,
                    'format': None,
                    'width': image_info.width,
                    'height': image_info.height,
                    'capture_date': image_info.capture_date
                }
                photo_id, = db.execute('INSERT INTO photos VALUES(:photo_id, :collection_id, 0, NULL, :format, :width, :height, NULL, :capture_date) '
                                       'ON CONFLICT DO UPDATE SET format = :format, width = :width, height = :height, capture_date = :capture_date '
                                       'RETURNING id', photos_data).fetchone()

                fs_data = {
                    'photo_id': photo_id,
                    'collection_id': self._id,
                    'path': local_path,
                    'modified_date': modified_date,
                    'scan_token': scan_token
                }
                db.execute('INSERT INTO fs_collections_data VALUES(:photo_id, :collection_id, :path, :modified_date, :scan_token) '
                           'ON CONFLICT DO UPDATE SET modified_date = :modified_date, scan_token = :scan_token', fs_data)

        if not cancellation_check():
            with db:
                deleted_count, = db.execute('SELECT COUNT(photo_id) FROM fs_collections_data WHERE collection_id = ? AND scan_token != ?',
                                            (self._id, scan_token)).fetchone()
                db.execute('WITH missing_photos AS (SELECT photo_id FROM fs_collections_data WHERE collection_id = ? AND scan_token != ?) '
                           'DELETE FROM photos WHERE id IN missing_photos', (self._id, scan_token))

        logger.info(f'Collection {self._identifier} refreshed. Added: {added_count}. Updated: {updated_count}. Deleted: {deleted_count}.')


class FileSystemCollection(Collection):
    def __init__(self, id: int, identifier: str, display_name: str,
                 schedule: str, enabled: bool, settings: dict[str, Any]):
        super().__init__(id, identifier, display_name, schedule, enabled, settings)
        self._root_path = _get_real_path(self._settings['root_path'])

    @staticmethod
    def get_settings_schema():
        class SettingsSchema(Schema):
            class Meta:
                ordered = True

            root_path = fields.String(required=True, metadata={'title': 'Path'})

        return SettingsSchema()

    @staticmethod
    def get_settings_default():
        return {
            'root_path': '~/photos'
        }

    @staticmethod
    def _get_process_class():
        return FileSystemCollectionProcess

    def get_photo_info(self, db: sqlite3.Connection, id: int):
        row = db.execute('SELECT path FROM fs_collections_data WHERE photo_id = ?', (id,)).fetchone()
        if not row:
            logger.error(f'No photo in collection {self.identifier} with id {id}')
            return None

        local_path = Path(row[0])
        absolute_path = self._root_path / local_path
        if not absolute_path.exists():
            return None

        return PhotoInfo(absolute_path.as_uri(), local_path, self.display_name)
