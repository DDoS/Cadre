import logging
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from amazon_photos import AmazonPhotos
from marshmallow import INCLUDE, Schema, fields
import pandas as pd

from ._base import Collection, CollectionProcess


logger = logging.getLogger('')


class AmazonPhotosCollectionProcess(CollectionProcess):
    def __init__(self, id: int, identifier: str, user_agent: str, cookies: dict[str, str]):
        super().__init__(id, identifier)
        self._user_agent = user_agent
        self._cookies = cookies

    def update(self, db: sqlite3.Connection, cancellation_check: Callable[[], bool]):
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS azp_collections_data('
                       'photo_id INTEGER PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE, '
                       'collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE, '
                       'node_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, modified_date TEXT NOT NULL, '
                       'update_token TEXT NOT NULL)')

        added_count = 0
        updated_count = 0
        deleted_count = 0
        update_token = '%016x' % random.randrange(16**16)

        def write_node_to_db(node: pd.Series):
            nonlocal added_count, updated_count

            node_id = node['id']
            modified_date: datetime = node['modifiedDate'].to_pydatetime().replace(tzinfo=timezone.utc)
            existing_data = db.execute('SELECT photo_id, modified_date as "d [datetime]" FROM azp_collections_data '
                                       'WHERE collection_id = ? AND node_id = ?', (self._id, node_id)).fetchone()

            photo_id: int = None
            if existing_data:
                photo_id, previous_modified_date = existing_data
                if previous_modified_date and modified_date <= previous_modified_date:
                    with db:
                        db.execute('UPDATE azp_collections_data SET update_token = ? WHERE photo_id = ?', (update_token, photo_id))
                    return

            if photo_id is None:
                added_count += 1
            else:
                updated_count += 1

            content_date: pd.Timestamp = node['contentDate']
            capture_date = None if pd.isna(content_date) else content_date.to_pydatetime().replace(tzinfo=None).astimezone()
            with db:
                photos_data = {
                    'photo_id': photo_id,
                    'collection_id': self._id,
                    'format': None,
                    'width': node['image.width'],
                    'height': node['image.height'],
                    'capture_date': capture_date
                }
                photo_id, = db.execute('INSERT INTO photos VALUES(:photo_id, :collection_id, 0, NULL, :format, :width, :height, NULL, :capture_date) '
                                       'ON CONFLICT DO UPDATE SET format = :format, width = :width, height = :height, capture_date = :capture_date '
                                       'RETURNING id', photos_data).fetchone()

                azp_data = {
                    'photo_id': photo_id,
                    'collection_id': self._id,
                    'node_id': node_id,
                    'name': node['name'],
                    'modified_date': modified_date,
                    'update_token': update_token
                }
                db.execute('INSERT INTO azp_collections_data VALUES(:photo_id, :collection_id, :node_id, :name, :modified_date, :update_token) '
                           'ON CONFLICT DO UPDATE SET node_id = :node_id, name = :name, modified_date = :modified_date, update_token = :update_token',
                        azp_data)

        amazon_photos = AmazonPhotos(self._cookies, self._user_agent, logger=logger)
        current_offset = 0
        batch_size = 10_000
        while not cancellation_check():
            if current_offset >= 10_000_000: # Safeguard
                break

            data_frame: pd.DataFrame = amazon_photos.photos(offset=current_offset, limit=current_offset + batch_size)
            current_offset += len(data_frame.index)
            if data_frame.empty:
                break

            for _, node in data_frame.iterrows():
                write_node_to_db(node)

        if not cancellation_check():
            with db:
                deleted_count, = db.execute('SELECT COUNT(photo_id) FROM azp_collections_data WHERE collection_id = ? AND update_token != ?',
                                            (self._id, update_token)).fetchone()
                db.execute('WITH missing_photos AS (SELECT photo_id FROM azp_collections_data WHERE collection_id = ? AND update_token != ?) '
                           'DELETE FROM photos WHERE id IN missing_photos', (self._id, update_token))

        logger.info(f'Collection {self._identifier} refreshed. Added: {added_count}. Updated: {updated_count}. Deleted: {deleted_count}.')

        if cancellation_check():
            logger.info(f'Update was cancelled')


class AmazonPhotosCollection(Collection):
    def __init__(self, id: int, identifier: str, display_name: str,
                 schedule: str, enabled: bool, settings: dict[str, Any]):
        super().__init__(id, identifier, display_name, schedule, enabled, settings)
        self._user_agent: dict[str, str] = self._settings['user_agent']
        self._cookies: dict[str, str] = self._settings['cookies'].copy()

        hidden_cookies: dict[str, str] = self._settings['cookies']
        for name in hidden_cookies:
            hidden_cookies[name] = '***'

    def _merge_settings(self, other_settings: dict[str, Any] | None = None):
        other_settings = super()._merge_settings(other_settings)

        other_cookies: dict[str, str]
        if other_cookies := other_settings.get('cookies'):
            for name, value in other_cookies.items():
                if re.fullmatch(r'\*+', value):
                    other_cookies[name] = self._cookies[name]

        return other_settings

    @staticmethod
    def get_settings_schema():
        class SettingsSchema(Schema):
            class Meta:
                ordered = True

            class Cookies(Schema):
                class Meta:
                    ordered = True
                    unknown = INCLUDE

            user_agent = fields.String(required=True, metadata={'title': 'User agent'})
            cookies = fields.Nested(Cookies, required=True, metadata={'title': 'Cookies'})

        return SettingsSchema()

    @staticmethod
    def get_settings_default():
        return {
            'user_agent': '',
            'cookies': {
            }
        }

    @staticmethod
    def _get_process_class():
        return AmazonPhotosCollectionProcess

    def get_photo_url(self, db: sqlite3.Connection, id: int):
        row = db.execute('SELECT node_id FROM azp_collections_data WHERE photo_id = ?', (id,)).fetchone()
        if not row:
            logger.error(f'No photo in collection {self.identifier} with id {id}')
            return None

        out_directory = Path(__file__).parent / 'azp_temp'
        AmazonPhotosCollection._cleanup_out_directory(out_directory)

        node_id: str = row[0]
        amazon_photos = AmazonPhotos(self._cookies, self._user_agent, logger=logger)
        amazon_photos.download([node_id], out=out_directory)
        for photo_path in out_directory.glob(f'{node_id}_*'):
            return photo_path.as_uri()

        logger.error(f'Node {node_id} download did not output a prefixed file in "{out_directory}"')
        return None

    @staticmethod
    def _cleanup_out_directory(path: Path):
        if not path.exists():
            return

        now_time = datetime.now()
        cleanup_timeout = timedelta(hours=1)
        with os.scandir(path) as iter:
            for entry in iter:
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue

                    access_time = datetime.fromtimestamp(entry.stat().st_atime)
                    if now_time - access_time >= cleanup_timeout:
                        os.unlink(entry.path)
                except OSError:
                    logger.exception('Can\'t cleanup old downloads')
