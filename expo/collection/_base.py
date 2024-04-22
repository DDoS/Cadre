import inspect
import sqlite3
import queue
import time
import signal
import json
import logging
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from importlib import import_module
from abc import ABCMeta, abstractmethod
from logging.config import dictConfig
from dataclasses import dataclass
from typing import Any, Callable

from croniter import croniter
from marshmallow import Schema, ValidationError, fields

import photo_db
from ._filter import Filter


collection_logger = logging.getLogger('collection')

mp.set_start_method('spawn', True)


@dataclass
class _StopMessage:
    pass


@dataclass
class _UpdateMessage:
    delay: float = 0


_ProcessMessage = _StopMessage | _UpdateMessage


class CollectionProcess:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, id: int, identifier: str):
        self._id = id
        self._identifier = identifier

    @abstractmethod
    def update(self, db: sqlite3.Connection, cancellation_check: Callable[[], bool]):
        raise NotImplementedError()


class Collection:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, id: int | None, identifier: str, display_name: str,
                 schedule: str, enabled: bool, settings: dict[str, Any]):
        if not photo_db.validate_identifier(identifier):
            raise ValueError('Invalid identifier')

        if errors := self.__class__.get_settings_schema().validate(settings):
            raise ValidationError(errors, data=settings)

        self._id = id
        self._identifier = identifier
        self._display_name = display_name
        self._schedule = schedule
        self._settings = settings
        self._enabled = enabled
        self._queue = None
        self._process = None

    @property
    def identifier(self):
        return self._identifier

    @property
    def display_name(self):
        return self._display_name

    @property
    def schedule(self):
        return self._schedule

    @property
    def enabled(self):
        return self._enabled

    @property
    def class_name(self):
        return self.__class__.__name__

    @property
    def settings(self):
        return self._settings

    def _set_id(self, id: int):
        self._id = id

    @staticmethod
    @abstractmethod
    def get_settings_schema() -> Schema:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def get_settings_default() -> dict[str, Any]:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def _get_process_class() -> type[CollectionProcess]:
        raise NotImplementedError()

    def start(self, photo_db_path: Path):
        if not self._enabled:
            raise ValueError('Can\'t start a disabled collection')

        process_class = self.__class__._get_process_class()

        self._queue = mp.Queue()
        self._process = mp.Process(target=_start_process, args=(self._queue, photo_db_path, self._id, self._identifier,
                                                                self._schedule, process_class, self._settings))
        self._process.start()

    def manual_update(self, delay: float = 0):
        if self._process is not None and self._queue is not None:
            self._queue.put(_UpdateMessage(delay))

    @abstractmethod
    def get_photo_url(self, db: sqlite3.Connection, id: int) -> str | None:
        raise NotImplementedError()

    def stop(self):
        if self._process is not None and self._queue is not None:
            self._queue.put(_StopMessage())
            self._process.join()
            self._queue.close()

        self._process = None
        self._queue = None


class DummyCollectionProcess(CollectionProcess):
    def __init__(self, id: int, identifier: str):
        super().__init__(id, identifier)

    def update(self, db: sqlite3.Connection, cancellation_check: Callable[[], bool]):
        pass


class DummyCollection(Collection):
    def __init__(self, id: int, identifier: str, display_name: str,
                 schedule: str, enabled: bool, settings: dict[str, Any]):
        super().__init__(id, identifier, display_name, schedule, enabled, settings)

    @staticmethod
    def get_settings_schema():
        class SettingsSchema(Schema):
            class Inner(Schema):
                numbers = fields.List(fields.Float())
                boolean = fields.DateTime()

            text = fields.String()
            inner = fields.Nested(Inner)

        return SettingsSchema()

    @staticmethod
    def get_settings_default():
        return {
            'text': 'test',
            'inner': {
                'numbers': [3, 39],
                'boolean': True
            }
        }

    @staticmethod
    def _get_process_class():
        return DummyCollectionProcess

    def get_photo_url(self, db: sqlite3.Connection, id: int):
        return None


_collection_classes_by_name: dict[str, type[Collection]] | None = None


def _get_collection_classes() -> dict[str, type[Collection]]:
    global _collection_classes_by_name

    if _collection_classes_by_name is None:
        _collection_classes_by_name = dict()
        class_module = import_module('collection')
        classes = inspect.getmembers(class_module, inspect.isclass)
        for name, class_ in classes:
            if issubclass(class_, Collection) and class_ != Collection:
                _collection_classes_by_name[name] = class_

    return _collection_classes_by_name


def get_collection_class_names() -> dict[str]:
    return _get_collection_classes().keys()


def _collection_class_from_name(class_name: str) -> type[Collection]:
    return _get_collection_classes()[class_name]


def get_collection_settings_schema(class_name: str) -> Schema | None:
    try:
        return _collection_class_from_name(class_name).get_settings_schema()
    except KeyError:
        return None


_collections_by_identifier: None | dict[int, Collection] = None


def _create_collection(db: sqlite3.Connection, id: int | None, identifier: str, display_name: str,
                       schedule: str, enabled: bool, class_name: str, settings: dict[str, Any]) -> Collection:
    CollectionClass = _collection_class_from_name(class_name)
    collection = CollectionClass(id, identifier, display_name, schedule, enabled, settings)

    row = {
        'id': id,
        'identifier': collection.identifier,
        'display_name': collection.display_name,
        'schedule': collection.schedule,
        'enabled': collection.enabled,
        'class_name': collection.class_name,
        'settings_json': json.dumps(collection.settings)
    }
    with db:
        id, = db.execute('INSERT INTO collections VALUES(:id, :identifier, :display_name, :schedule, :enabled, :class_name, :settings_json) '
                         'ON CONFLICT(id) DO UPDATE SET identifier = :identifier, display_name = :display_name, schedule = :schedule, '
                         'enabled = :enabled, class_name = :class_name, settings_json = :settings_json RETURNING id', row).fetchone()

    collection._set_id(id)
    return collection


def init_collections(photo_db_path: Path):
    global _collections_by_identifier
    if _collections_by_identifier is not None:
        return

    # Can't use atexit to stop processes, so do it in SIGINT handler
    previous_signal_handler = signal.getsignal(signal.SIGINT)
    def at_exit_request(sig_number, frame):
        for collection in _collections_by_identifier.values():
            collection_logger.info(f'Stopping "{collection.identifier}"')
            collection.stop()

        collection_logger.info('Stopped all collections')

        if callable(previous_signal_handler):
            previous_signal_handler(sig_number, frame)

    signal.signal(signal.SIGINT, at_exit_request)

    collections: list[Collection] = []
    try:
        db = photo_db.open(photo_db_path)
        for row in db.execute('SELECT id, identifier, display_name, schedule, enabled, class_name, settings_json FROM collections'):
            class_name = row[5]
            CollectionClass = _collection_class_from_name(class_name)
            collections.append(CollectionClass(row[0], row[1], row[2], row[3], bool(row[4]), json.loads(row[6])))
    except Exception:
        collection_logger.exception('Invalid collection in the photo DB')
    finally:
        db.close()

    for collection in collections:
        if collection.enabled:
            collection_logger.info(f'Starting "{collection.identifier}"')
            collection.start(photo_db_path)

    collection_logger.info('Started all collections')

    _collections_by_identifier = { collection.identifier: collection for collection in collections }


def get_collections():
    return _collections_by_identifier.values() if _collections_by_identifier is not None else []


def get_collection(identifier: str) -> Collection | None:
    if has_collection(identifier):
        return _collections_by_identifier[identifier]

    return None


def has_collection(identifier: str):
    return identifier in _collections_by_identifier


def add_collection(photo_db_path: Path, identifier: str, display_name: str,
                   schedule: str, enabled: bool, class_name: str, settings: dict[str, Any]) -> Collection:
    if identifier in _collections_by_identifier:
        raise KeyError(f'Already in use: "{identifier}"')

    try:
        db = photo_db.open(photo_db_path)
        collection = _create_collection(db, None, identifier, display_name, schedule, enabled, class_name, settings)
        collection_logger.info(f'Added "{collection.identifier}"')
    finally:
        db.close()

    _collections_by_identifier[collection.identifier] = collection
    if collection.enabled:
        collection.start(photo_db_path)

    return collection


def modify_collection(photo_db_path: Path, collection: Collection, identifier: str = None, display_name: str = None,
                      schedule: str = None, enabled: bool = None, class_name: str = None, settings: dict[str, Any] = None) -> Collection:
    old_identifier = collection.identifier
    if identifier is not None and identifier != old_identifier and identifier in _collections_by_identifier:
        raise KeyError(f'Already in use: "{identifier}"')

    if identifier is None:
        identifier = collection.identifier
    if display_name is None:
        display_name = collection.display_name
    if schedule is None:
        schedule = collection.schedule
    if enabled is None:
        enabled = collection.enabled
    if class_name is None:
        class_name = collection.class_name
    if settings is None:
        settings = collection.settings

    collection.stop()

    try:
        db = photo_db.open(photo_db_path)
        collection = _create_collection(db, collection._id, identifier, display_name, schedule, enabled, class_name, settings)
        collection_logger.info(f'Modified "{identifier}"')
    finally:
        db.close()

    _collections_by_identifier[collection.identifier] = collection
    if collection.identifier != old_identifier:
        del _collections_by_identifier[old_identifier]

    if collection.enabled:
        collection.start(photo_db_path)

    return collection


def remove_collection(photo_db_path: Path, collection: Collection):
    collection.stop()
    del _collections_by_identifier[collection.identifier]

    try:
        db = photo_db.open(photo_db_path)
        with db:
            db.execute('DELETE FROM collections WHERE identifier = ?', (collection.identifier,))
        collection_logger.info(f'Removed "{collection.identifier}"')
    finally:
        db.close()


def get_new_photo_url(photo_db_path: Path, filter: Filter) -> str | None:
    try:
        db = photo_db.open(photo_db_path)
        sql_filter = filter.to_sql()
        collection_logger.debug(f'Generated SQLite filter: "{sql_filter}"')
        # Nested SELECT query for random selection is much faster: https://stackoverflow.com/a/24591696
        row = db.execute('SELECT id, collection_id FROM (SELECT id, collection_id, display_date FROM photos WHERE id IN '
                         '(SELECT photos.id FROM photos INNER JOIN collections ON collections.id = photos.collection_id WHERE '
                         f'collections.enabled AND ({sql_filter}) ORDER BY RANDOM() LIMIT 2)) ORDER BY datetime(display_date) '
                         'ASC LIMIT 1').fetchone()
        if not row:
            return None

        photo_id, collection_id = row
        with db:
            new_display_date = datetime.now().astimezone()
            db.execute('UPDATE photos SET display_date = ? WHERE id = ?', (new_display_date, photo_id))

        photo_url: str | None = None
        for collection in _collections_by_identifier.values():
            if collection._id == collection_id:
                photo_url = collection.get_photo_url(db, photo_id)
                collection_logger.debug(f'selected photo "{photo_url}" from "{collection.identifier}"')
                break

        return photo_url
    finally:
        db.close()


def _start_process(message_queue: mp.Queue, photo_db_path: Path, id: int, identifier: str, schedule: str,
                   CollectionProcessClass: type[CollectionProcess], settings: dict[str, Any]):
    dictConfig({
        'version': 1,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            }
        },
        'handlers': {
            'file.handler': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': str(Path(__file__).parent / f'{CollectionProcessClass.__name__}_{identifier}.log'),
                'maxBytes': 1_000_000,
                'backupCount': 2,
                'level': 'INFO',
                'formatter': 'standard'
            },
        },
        'loggers': {
            '': {
                'level': 'DEBUG',
                'handlers': ['file.handler']
            }
        }
    })

    logger = logging.getLogger('')
    logger.info(f'Starting {identifier}')

    next_update_time: float | None = None
    def update_next_update_time(candidate_update_time: float):
        nonlocal next_update_time

        if next_update_time is not None and next_update_time < time.time():
            next_update_time = None

        if next_update_time is None or candidate_update_time < next_update_time:
            next_update_time = candidate_update_time
            logger.debug(f'Next update: {datetime.fromtimestamp(next_update_time).isoformat()}')

    running = True
    def check_running(block: bool = True, timeout: float = None) -> bool:
        nonlocal running

        if running:
            try:
                match message_queue.get(block, timeout):
                    case _StopMessage():
                        running = False
                    case _UpdateMessage(delay):
                        update_next_update_time(time.time() + delay)
            except queue.Empty:
                pass

        return running

    schedule_iterator = croniter(schedule)
    def wait_for_next_update():
        update_next_update_time(schedule_iterator.get_next(start_time=time.time()))

        while running:
            time_left = next_update_time - time.time()
            if time_left <= 0 or not check_running(timeout=time_left):
                break

        return running

    collection: CollectionProcess = CollectionProcessClass(id, identifier, **settings)
    logger.info(f'Started {identifier}')
    while wait_for_next_update():
        db = photo_db.open(photo_db_path)
        try:
            logger.info(f'Updating {identifier}')
            collection.update(db, lambda: not check_running(block=False))
        except Exception:
            logger.exception(f'Error in collection {identifier} update')
        finally:
            db.close()

    logger.info(f'Stopped {identifier}')
