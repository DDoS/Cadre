import signal
import logging
from pathlib import Path
from logging.config import dictConfig
from typing import Any

from flask import Flask, request
from marshmallow import Schema, fields, ValidationError

import photo_db
from collection import *
from refresh_job import *


# Make sure we can shutdown using SIGINT
if signal.getsignal(signal.SIGINT) == signal.SIG_IGN:
    signal.signal(signal.SIGINT, signal.default_int_handler)


expo_logger = logging.getLogger('expo')


SERVER_PATH = Path(__file__).parent

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
            'filename': str(SERVER_PATH / 'app.log'),
            'maxBytes': 1_000_000,
            'backupCount': 2,
            'level': 'INFO',
            'formatter': 'standard'
        }
    },
    'loggers': {
        __name__: {
            'level': 'DEBUG',
            'handlers': ['file.handler']
        },
        'expo': {
            'level': 'DEBUG',
            'handlers': ['file.handler']
        },
        'collection': {
            'level': 'DEBUG',
            'handlers': ['file.handler']
        },
        'refresh_job': {
            'level': 'DEBUG',
            'handlers': ['file.handler']
        },
        'werkzeug': {
            'level': 'INFO',
            'handlers': ['file.handler']
        }
    }
})


PHOTO_DB_PATH = SERVER_PATH / 'photos.db'
photo_db.setup(PHOTO_DB_PATH)
init_collections(PHOTO_DB_PATH)
init_refresh_jobs(PHOTO_DB_PATH)


app = Flask(__name__)

@app.route('/')
def root():
    return 'Expo', 200


@app.route('/refresh', methods=['POST'])
def refresh():
    class RefreshSchema(Schema):
        identifier = fields.String(required=True)
        delay = fields.Number(load_default=0)

    try:
        result = RefreshSchema().load(request.json)
    except ValidationError as error:
        return error.messages, 400

    job = get_refresh_job(result['identifier'])
    if not job:
        return 'No schedule for the given identifier', 404

    delay = max(0, float(result['delay']))
    job.manual_refresh(delay)

    return '', 200


@app.route('/collections', methods=['PUT', 'GET', 'PATCH', 'DELETE'])
def collections():
    def collection_to_dict(collection: Collection):
        return {
            'identifier': collection.identifier,
            'display_name': collection.display_name,
            'schedule': collection.schedule,
            'class_name': collection.class_name,
            'settings': collection.settings
        }

    identifier = request.args.get('identifier')
    if identifier is None:
        if request.method == 'GET':
            response = []
            for collection in get_collections():
                response.append(collection_to_dict(collection))

            return response, 200

        if request.method == 'PUT':
            class PutCollectionSchema(Schema):
                identifier = fields.String(required=True)
                display_name = fields.String()
                schedule = fields.String(required=True)
                class_name = fields.String(required=True)
                settings = fields.Dict(load_default={})

            try:
                result = PutCollectionSchema().load(request.json)
            except ValidationError as error:
                return error.messages, 400

            try:
                identifier = result['identifier']
                if has_collection(identifier):
                    return 'A collection for the given identifier already exists', 400

                collection = add_collection(PHOTO_DB_PATH, identifier, result.get('display_name', identifier),
                                            result['schedule'], result['class_name'], result['settings'])
                app.logger.info(f'Added collection "{identifier}"')
                return collection_to_dict(collection), 200
            except ValidationError as error:
                return error.messages, 400
            except Exception:
                app.logger.debug('Invalid arguments', exc_info=True)
                return 'Invalid arguments', 400

        return 'Parameter "identifier" required', 400

    collection = get_collection(identifier)
    if not collection:
        return 'No collection for the given identifier', 404

    if request.method == 'GET':
        return collection_to_dict(collection), 200

    if request.method == 'DELETE':
        remove_collection(PHOTO_DB_PATH, collection)
        app.logger.info(f'Removed collection "{identifier}"')
        return '', 200

    if request.method == 'PATCH':
        class PatchCollectionSchema(Schema):
            identifier = fields.String()
            display_name = fields.String()
            schedule = fields.String()
            class_name = fields.String()
            settings = fields.Dict()

        try:
            result = PatchCollectionSchema().load(request.json)
        except ValidationError as error:
            return error.messages, 400

        try:
            collection = modify_collection(PHOTO_DB_PATH, collection, result.get('identifier'), result.get('display_name'),
                                           result.get('schedule'), result.get('class_name'), result.get('settings'))
            app.logger.info(f'Modified collection "{identifier}"')
            return collection_to_dict(collection), 200
        except Exception:
            app.logger.debug('Invalid arguments', exc_info=True)
            return 'Invalid arguments', 400


@app.route('/schedules', methods=['PUT', 'GET', 'PATCH', 'DELETE'])
def schedules():
    def refresh_job_to_dict(job: RefreshJob):
        return {
            'identifier': job.identifier,
            'display_name': job.display_name,
            'hostname': job.hostname,
            'schedule': job.schedule,
            'enabled': job.enabled,
            'filter': str(job.filter)
        }

    identifier = request.args.get('identifier')
    if identifier is None:
        if request.method == 'GET':
            response = []
            for job in get_refresh_jobs():
                response.append(refresh_job_to_dict(job))

            return response, 200

        if request.method == 'PUT':
            class PutRefreshJobSchema(Schema):
                identifier = fields.String(required=True)
                display_name = fields.String()
                hostname = fields.String(required=True)
                schedule = fields.String(required=True)
                enabled = fields.Boolean(load_default=True)
                filter = fields.String(load_default='true')

            try:
                result = PutRefreshJobSchema().load(request.json)
            except ValidationError as error:
                return error.messages, 400

            try:
                identifier = result['identifier']
                if has_refresh_job(identifier):
                    return 'A schedule for the given identifier already exists', 400

                job = add_refresh_job(PHOTO_DB_PATH, identifier, result.get('display_name', identifier),
                                      result['hostname'], result['schedule'], result['enabled'], result['filter'])
                app.logger.info(f'Added refresh job "{identifier}"')
                return refresh_job_to_dict(job), 200
            except Exception:
                app.logger.debug('Invalid arguments', exc_info=True)
                return 'Invalid arguments', 400

        return 'Parameter "identifier" required', 400

    job = get_refresh_job(identifier)
    if not job:
        return 'No schedule for the given identifier', 404

    if request.method == 'GET':
        return refresh_job_to_dict(job), 200

    if request.method == 'DELETE':
        remove_refresh_job(PHOTO_DB_PATH, job)
        app.logger.info(f'Removed refresh job "{identifier}"')
        return '', 200

    if request.method == 'PATCH':
        class PatchRefreshJobSchema(Schema):
            identifier = fields.String()
            display_name = fields.String()
            hostname = fields.String()
            schedule = fields.String()
            enabled = fields.Boolean()
            filter = fields.String()

        try:
            result = PatchRefreshJobSchema().load(request.json)
        except ValidationError as error:
            return error.messages, 400

        try:
            job = modify_refresh_job(PHOTO_DB_PATH, job, result.get('identifier'), result.get('display_name'),
                                     result.get('hostname'), result.get('schedule'), result.get('enabled'), result.get('filter'))
            app.logger.info(f'Modified refresh job "{identifier}"')
            return refresh_job_to_dict(job), 200
        except Exception:
            app.logger.debug('Invalid arguments', exc_info=True)
            return 'Invalid arguments', 400
