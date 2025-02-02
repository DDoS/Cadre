import atexit
import ipaddress
import json
import logging
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from croniter import croniter
import requests

import expo_db
from collection import get_new_photo, parse_filter, Filter, Order, PhotoInfo

sys.path.append(str(Path(__file__).absolute().parent.parent / 'cru'))
import cru_utils


# socket.getfqdn is broken on macOS, but platform.node() should return the correct value
def get_external_hostname():
    import platform
    if platform.system() == 'Darwin':
        return platform.node()

    return socket.getfqdn()


refresh_job_logger = logging.getLogger('refresh_job')


if not cru_utils.available:
    refresh_job_logger.error('cru module not found: image info will not be available.')


refresh_scheduler = BackgroundScheduler()
refresh_scheduler.start()
atexit.register(lambda: refresh_scheduler.shutdown())


class RefreshJob:
    post_commands_by_id: dict[str, list[str]]

    def __init__(self, id: int | None, identifier: str, display_name: str,
                 hostname: str, schedule: str, enabled: bool, filter: str | Filter,
                 order: str | Order, affiche_options: dict[str, Any], post_command_id: str):
        if not expo_db.validate_identifier(identifier):
            raise ValueError('Invalid identifier')
        if len(schedule) > 0 and not croniter.is_valid(schedule):
            raise ValueError('Invalid schedule')

        self._id = id
        self._identifier = identifier
        self._display_name = display_name
        self._hostname = hostname
        self._is_local_address = RefreshJob._hostname_is_local(hostname)
        self._schedule = schedule
        self._enabled = enabled
        self._filter = filter if isinstance(filter, Filter) else parse_filter(filter)
        self._order = order if isinstance(order, Order) else Order[order]
        self._affiche_options = affiche_options
        self._post_command_id = post_command_id
        self._job: Job | None = None


    @property
    def identifier(self):
        return self._identifier


    @property
    def display_name(self):
        return self._display_name


    @property
    def hostname(self):
        return self._hostname


    @property
    def external_hostname(self):
        if not self._is_local_address:
            return self.hostname

        external_hostname = get_external_hostname()
        if ':' in self._hostname:
            external_hostname += f':{self._hostname.split(":")[1]}'

        return external_hostname


    @property
    def schedule(self):
        return self._schedule


    @property
    def enabled(self):
        return self._enabled


    @property
    def filter(self):
        return self._filter


    @property
    def order(self):
        return self._order


    @property
    def affiche_options(self):
        return self._affiche_options


    @property
    def post_command_id(self):
        return self._post_command_id


    def start(self, db_path: Path):
        if not self._enabled:
            raise ValueError('Can\'t start a disabled refresh job')

        if not self._schedule:
            return

        # Not using CronTrigger to ensure a consistent cron notation with collections
        schedule_iterator = croniter(self._schedule, ret_type=datetime)

        def refresh_and_reschedule(start=False):
            if not start:
                self._refresh(db_path)
                if not self._job:
                    return

            next_date: datetime = schedule_iterator.get_next(start_time=datetime.now().astimezone())
            refresh_job_logger.debug(f'Next refresh: {next_date.isoformat()}')
            self._job = refresh_scheduler.add_job(refresh_and_reschedule, trigger=DateTrigger(next_date),
                                                  misfire_grace_time=60, coalesce=True)

        refresh_and_reschedule(True)


    def _refresh(self, db_path: Path):
        try:
            refresh_job_logger.info(f'Running refresh job "{self._identifier}"')
            if photo_info := get_new_photo(db_path, self._filter, self._order):
                refresh_job_logger.info(f'Posting: "{photo_info.url}" to {self._hostname}')
                self._post_photo(photo_info)
            else:
                refresh_job_logger.info('No image available for refresh')
        except Exception:
            refresh_job_logger.exception('Failed to post an image to Affiche')


    def manual_refresh(self, db_path: Path, delay: float = 0):
        if not self._enabled:
            raise ValueError('Can\'t refresh a disabled job')

        trigger_date = datetime.now().astimezone() + timedelta(seconds=delay)
        if self._job and refresh_scheduler.get_job(self._job.id):
            self._job.modify(next_run_time=trigger_date)
        else:
            refresh_scheduler.add_job(lambda: self._refresh(db_path), trigger=DateTrigger(trigger_date))


    def stop(self):
        if not self._job:
            return

        job_id = self._job.id
        self._job = None

        try:
            refresh_scheduler.remove_job(job_id)
        except JobLookupError:
            pass


    def _post_photo(self, photo_info: PhotoInfo):
        host_url = f'http://{self._hostname}'

        info = {
            'path': photo_info.path_info,
            'collection': photo_info.collection_info
        }

        if self.post_command_id:
            command = RefreshJob.post_commands_by_id.get(self.post_command_id)
            if not command:
                refresh_job_logger.error(f'No post command for ID "{self.post_command_id}"')
            else:
                refresh_job_logger.info(f'Using post command "{self.post_command_id}"')
                self._post_with_command(command, photo_info.url, info)
            return

        data = {'info': json.dumps(info)}
        for name, value in self.affiche_options.items():
            data[f'options.{name}'] = value

        # If we have a local file for a non-local address, then
        # we need to stream the content instead of sending the URL.
        if not self._is_local_address:
            if photo_path := RefreshJob._try_get_local_path(photo_info.url):
                requests.post(host_url, files={'file': open(photo_path, 'rb')},
                              data=data).raise_for_status()
                return

        data['url'] = photo_info.url
        requests.post(host_url, data=data).raise_for_status()


    def _post_with_command(self, command: list[str], url: str, info: dict[str, str]):
        photo_path = RefreshJob._try_get_local_path(url)
        if not photo_path:
            refresh_job_logger.error('Posting photos with custom commands from non-local URL is not supported.'
                                     f' URL was: "{url}"')
            return

        if image_info := cru_utils.get_image_info_dict(photo_path):
            info.update(image_info)

        command = [arg.replace('%HOSTNAME%', self.hostname) for arg in command]
        full_command = [*command, str(photo_path), '--options', json.dumps(self.affiche_options),
                        '--info', json.dumps(info)]
        refresh_job_logger.debug(f'Running post command: {" ".join(repr(arg) for arg in full_command)}')
        result = subprocess.run(full_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, bufsize=1)
        if result.returncode:
            refresh_job_logger.error(f'Post command failed with result code {result.returncode}.'
                                     f' Output:\n{result.stdout}')
        else:
            refresh_job_logger.debug(f'Post command output:\n{result.stdout}')


    @staticmethod
    def _try_get_local_path(url: str) -> Path | None:
        parsed_url = urlparse(url)
        if not parsed_url.scheme in ('file', ''):
            return None

        return Path(unquote(parsed_url.path))


    @staticmethod
    def _hostname_is_local(hostname: str):
        try:
            hostname_and_port = hostname.split(':')
            port = hostname_and_port[1] if len(hostname_and_port) > 1 else 80
            addresses = socket.getaddrinfo(hostname_and_port[0], port, family=socket.AF_INET,
                                           type=socket.SOCK_STREAM, proto=socket.IPPROTO_IP)
            for _, _, _, _, (address, _) in addresses:
                if ipaddress.ip_address(address).is_loopback:
                    return True
        except Exception:
            raise ValueError(f'Invalid hostname: {hostname}')

        return False


_refresh_jobs_by_identifier: dict[str, RefreshJob] | None = None


def _create_refresh_job(db: sqlite3.Connection, id: int | None, identifier: str, display_name: str,
                       hostname: str, schedule: str, enabled: bool, filter: str | Filter,
                       order: str | Order, affiche_options: dict[str, Any], post_command_id: str) -> RefreshJob:
    job = RefreshJob(id, identifier, display_name, hostname, schedule,
                     enabled, filter, order, affiche_options, post_command_id)

    row = {
        'id': id,
        'identifier': job.identifier,
        'display_name': job.display_name,
        'hostname': job.hostname,
        'schedule': job.schedule,
        'enabled': job.enabled,
        'filter': str(job.filter),
        'order': job.order.name,
        'affiche_options_json': json.dumps(job.affiche_options),
        'post_command_id': job.post_command_id,
    }
    with db:
        id, = db.execute('INSERT INTO refresh_jobs VALUES(:id, :identifier, :display_name, :hostname, :schedule, :enabled, '
                         ':filter, :order, :affiche_options_json, :post_command_id) ON CONFLICT(id) DO UPDATE SET '
                         'identifier = :identifier, display_name = :display_name, hostname = :hostname, schedule = :schedule, '
                         'enabled = :enabled, filter = :filter, "order" = :order, affiche_options_json = :affiche_options_json, '
                         'post_command_id = :post_command_id RETURNING id', row).fetchone()

    job._id = id
    return job


def init_refresh_jobs(db_path: Path):
    global _refresh_jobs_by_identifier
    if _refresh_jobs_by_identifier is not None:
        return

    refresh_jobs: list[RefreshJob] = []
    try:
        db = expo_db.open(db_path)
        for row in db.execute('SELECT id, identifier, display_name, hostname, schedule, enabled, '
                              'filter, "order", affiche_options_json, post_command_id FROM refresh_jobs'):
            refresh_jobs.append(RefreshJob(row[0], row[1], row[2], row[3], row[4], bool(row[5]),
                                           row[6], row[7], json.loads(row[8]), row[9]))
    except Exception:
        refresh_job_logger.exception('Invalid refresh job in the photo DB')
    finally:
        db.close()

    for job in refresh_jobs:
        if job.enabled:
            refresh_job_logger.info(f'Starting "{job.identifier}"')
            job.start(db_path)

    refresh_job_logger.info('Scheduled all refreshes')

    _refresh_jobs_by_identifier = { refresh_job.identifier: refresh_job for refresh_job in refresh_jobs }


def get_refresh_jobs():
    return _refresh_jobs_by_identifier.values() if _refresh_jobs_by_identifier is not None else []


def get_refresh_job(identifier: str) -> RefreshJob | None:
    if has_refresh_job(identifier):
        return _refresh_jobs_by_identifier[identifier]

    return None


def has_refresh_job(identifier: str):
    return identifier in _refresh_jobs_by_identifier


def add_refresh_job(db_path: Path, identifier: str, display_name: str,
                    hostname: str, schedule: str, enabled: bool, filter: str | Filter,
                    order: str | Order, affiche_options: dict[str, Any], post_command_id: str) -> RefreshJob:
    if identifier in _refresh_jobs_by_identifier:
        raise KeyError(f'Already in use: "{identifier}"')

    try:
        db = expo_db.open(db_path)
        job = _create_refresh_job(db, None, identifier, display_name, hostname, schedule,
                                  enabled, filter, order, affiche_options, post_command_id)
        refresh_job_logger.info(f'Added "{job.identifier}"')
    finally:
        db.close()

    _refresh_jobs_by_identifier[job.identifier] = job
    if job.enabled:
        job.start(db_path)

    return job


def modify_refresh_job(db_path: Path, job: RefreshJob, identifier: str | None = None,
                       display_name: str | None = None, hostname: str | None = None, schedule: str | None = None,
                       enabled: bool | None = None, filter: str | Filter | None = None,
                       order: str | Order | None = None, affiche_options: dict[str, Any] | None = None,
                       post_command_id: str | None = None) -> RefreshJob:
    old_identifier = job.identifier
    if identifier is not None and identifier != old_identifier and identifier in _refresh_jobs_by_identifier:
        raise KeyError(f'Already in use: "{identifier}"')

    if identifier is None:
        identifier = job.identifier
    if display_name is None:
        display_name = job.display_name
    if hostname is None:
        hostname = job.hostname
    if schedule is None:
        schedule = job.schedule
    if enabled is None:
        enabled = job.enabled
    if filter is None:
        filter = job.filter
    if order is None:
        order = job.order
    if affiche_options is None:
        affiche_options = job.affiche_options
    if post_command_id is None:
        post_command_id = job.post_command_id

    job.stop()

    try:
        db = expo_db.open(db_path)
        job = _create_refresh_job(db, job._id, identifier, display_name, hostname, schedule,
                                  enabled, filter, order, affiche_options, post_command_id)
        refresh_job_logger.info(f'Modified "{identifier}"')
    finally:
        db.close()

    _refresh_jobs_by_identifier[job.identifier] = job
    if job.identifier != old_identifier:
        del _refresh_jobs_by_identifier[old_identifier]

    if job.enabled:
        job.start(db_path)

    return job


def remove_refresh_job(db_path: Path, job: RefreshJob):
    job.stop()
    del _refresh_jobs_by_identifier[job.identifier]

    try:
        db = expo_db.open(db_path)
        with db:
            db.execute('DELETE FROM refresh_jobs WHERE identifier = ?', (job.identifier,))
        refresh_job_logger.info(f'Removed "{job.identifier}"')
    finally:
        db.close()
