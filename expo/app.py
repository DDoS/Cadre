import signal
import logging
import os
from enum import Enum
from pathlib import Path
from logging.config import dictConfig

from flask import Flask, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from marshmallow import Schema, fields, ValidationError
from marshmallow.validate import OneOf, Regexp
from marshmallow_jsonschema import JSONSchema

import expo_db
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
            'level': 'DEBUG',
            'formatter': 'standard'
        }
    },
    'loggers': {
        __name__: {
            'level': 'INFO',
            'handlers': ['file.handler']
        },
        'expo': {
            'level': 'INFO',
            'handlers': ['file.handler']
        },
        'collection': {
            'level': 'INFO',
            'handlers': ['file.handler']
        },
        'refresh_job': {
            'level': 'INFO',
            'handlers': ['file.handler']
        },
        'werkzeug': {
            'level': 'INFO',
            'handlers': ['file.handler']
        }
    }
})


def setup_app_config(app: Flask):
    app.config.from_file('default_config.json', load=json.load)

    config_path = os.environ.get('EXPO_CONFIG_PATH', 'config.json')
    app.config.from_file(config_path, load=json.load, silent=True)

    db_path: Path = SERVER_PATH / app.config['DB_PATH']
    db_path.parent.mkdir(exist_ok=True)
    app.config['DB_PATH'] = db_path

    RefreshJob.post_commands_by_id = dict(app.config['POST_COMMANDS'])


def start_background_jobs(app: Flask):
    db_path = app.config['DB_PATH']
    expo_db.setup(db_path)
    init_collections(db_path)
    init_refresh_jobs(db_path)


class DefaultJSONProvider_EnumSupport(DefaultJSONProvider):
    @staticmethod
    def default(o):
        return o.name if isinstance(o, Enum) else DefaultJSONProvider.default(o)


Flask.json_provider_class = DefaultJSONProvider_EnumSupport
app = Flask(__name__)
app.json.sort_keys = False
app.json.include_nulls = True
CORS(app)
setup_app_config(app)
start_background_jobs(app)


@app.route('/')
def root():
    return app.send_static_file('index.html')


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
    if not job or not job.enabled:
        return 'No enabled schedule for the given identifier', 404

    delay = max(0, float(result['delay']))
    job.manual_refresh(app.config['DB_PATH'], delay)

    return '', 200


@app.route('/scan', methods=['POST'])
def scan():
    class ScanSchema(Schema):
        identifier = fields.String(required=True)
        delay = fields.Number(load_default=0)

    try:
        result = ScanSchema().load(request.json)
    except ValidationError as error:
        return error.messages, 400

    collection = get_collection(result['identifier'])
    if not collection or not collection.enabled:
        return 'No enabled collection for the given identifier', 404

    delay = max(0, float(result['delay']))
    collection.manual_update(delay)

    return '', 200


class CollectionSchema(Schema):
    class Meta:
        ordered = True

    identifier = fields.String(required=True, validate=Regexp(expo_db.identifier_pattern),
                               metadata={'title': 'Identifier'})
    display_name = fields.String(load_default='', metadata={'title': 'Name'})
    schedule = fields.String(required=True, metadata={'title': 'Schedule'})
    enabled = fields.Boolean(load_default=True, metadata={'title': 'Enabled'})
    class_name = fields.String(required=True, validate=OneOf(get_collection_class_names()),
                               metadata={'title': 'Class name'})
    settings = fields.Dict(load_default={}, metadata={'title': 'Settings'})


@app.route('/collections', methods=['PUT', 'GET', 'PATCH', 'DELETE'])
def collections():
    def collection_to_dict(collection: Collection):
        return {
            'identifier': collection.identifier,
            'display_name': collection.display_name,
            'schedule': collection.schedule,
            'enabled': collection.enabled,
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
            try:
                result = CollectionSchema().load(request.json)
            except ValidationError as error:
                return error.messages, 400

            try:
                identifier = result['identifier']
                if has_collection(identifier):
                    return 'A collection for the given identifier already exists', 400

                display_name = result.get('display_name')
                if not display_name:
                    display_name = identifier

                collection = add_collection(app.config['DB_PATH'], identifier, display_name,
                                            result['schedule'], result['enabled'], result['class_name'], result['settings'])
                app.logger.info(f'Added collection "{identifier}"')
                return collection_to_dict(collection), 200
            except ValidationError as error:
                return error.messages, 400
            except Exception as error:
                app.logger.debug('Invalid arguments', exc_info=True)
                return getattr(error, 'message', str(error)), 400

        return 'Parameter "identifier" required', 400

    collection = get_collection(identifier)
    if not collection:
        return 'No collection for the given identifier', 404

    if request.method == 'GET':
        return collection_to_dict(collection), 200

    if request.method == 'DELETE':
        remove_collection(app.config['DB_PATH'], collection)
        app.logger.info(f'Removed collection "{identifier}"')
        return '', 200

    if request.method == 'PATCH':
        class PatchCollectionSchema(Schema):
            identifier = fields.String()
            display_name = fields.String()
            schedule = fields.String()
            enabled = fields.Boolean()
            class_name = fields.String()
            settings = fields.Dict()

        try:
            result = PatchCollectionSchema().load(request.json)
        except ValidationError as error:
            return error.messages, 400

        try:
            collection = modify_collection(app.config['DB_PATH'], collection, result.get('identifier'), result.get('display_name'),
                                           result.get('schedule'), result.get('enabled'), result.get('class_name'), result.get('settings'))
            app.logger.info(f'Modified collection "{identifier}"')
            return collection_to_dict(collection), 200
        except Exception as error:
            app.logger.debug('Invalid arguments', exc_info=True)
            return getattr(error, 'message', str(error)), 400


class RefreshJobSchema(Schema):
    class Meta:
        ordered = True

    identifier = fields.String(required=True, validate=Regexp(expo_db.identifier_pattern),
                               metadata={'title': 'Identifier'})
    display_name = fields.String(load_default='', metadata={'title': 'Name'})
    hostname = fields.String(required=True, metadata={'title': 'Hostname'})
    schedule = fields.String(required=True, metadata={'title': 'Schedule'})
    enabled = fields.Boolean(load_default=True, metadata={'title': 'Enabled'})
    filter = fields.String(load_default='true', metadata={'title': 'Filter'})
    order = fields.Enum(Order, load_default=Order.SHUFFLE, metadata={'title': 'Order'})
    post_command_id = fields.String(load_default='', metadata={'title': 'Post command'},
                                    validate=OneOf(['', *RefreshJob.post_commands_by_id.keys()]))
    affiche_options = fields.Dict(load_default={}, metadata={'title': 'Affiche options'})


class RefreshJobSchema_MarshmallowJsonSchemaCompatibility(RefreshJobSchema):
    order = fields.String(load_default=Order.SHUFFLE.name, validate=OneOf(Order.__members__.keys()),
                          metadata={'title': 'Order'})


@app.route('/schedules', methods=['PUT', 'GET', 'PATCH', 'DELETE'])
def schedules():
    def refresh_job_to_dict(job: RefreshJob):
        return {
            'identifier': job.identifier,
            'display_name': job.display_name,
            'hostname': job.hostname,
            'schedule': job.schedule,
            'enabled': job.enabled,
            'filter': str(job.filter),
            'order': job.order.name,
            'post_command_id': job.post_command_id,
            'affiche_options': job.affiche_options,
        }

    identifier = request.args.get('identifier')
    if identifier is None:
        if request.method == 'GET':
            hostname = request.args.get('hostname')
            response = []
            for job in get_refresh_jobs():
                if not hostname or hostname == job.hostname or hostname == job.external_hostname:
                    response.append(refresh_job_to_dict(job))

            return response, 200

        if request.method == 'PUT':
            try:
                result = RefreshJobSchema().load(request.json)
            except ValidationError as error:
                return error.messages, 400

            try:
                identifier = result['identifier']
                if has_refresh_job(identifier):
                    return 'A schedule for the given identifier already exists', 400

                display_name = result.get('display_name')
                if not display_name:
                    display_name = identifier

                job = add_refresh_job(app.config['DB_PATH'], identifier, display_name,
                                      result['hostname'], result['schedule'], result['enabled'],
                                      result['filter'], result['order'], result['affiche_options'],
                                      result['post_command_id'])
                app.logger.info(f'Added refresh job "{identifier}"')
                return refresh_job_to_dict(job), 200
            except Exception as error:
                app.logger.debug('Invalid arguments', exc_info=True)
                return getattr(error, 'message', str(error)), 400

        return 'Parameter "identifier" required', 400

    job = get_refresh_job(identifier)
    if not job:
        return 'No schedule for the given identifier', 404

    if request.method == 'GET':
        return refresh_job_to_dict(job), 200

    if request.method == 'DELETE':
        remove_refresh_job(app.config['DB_PATH'], job)
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
            order = fields.Enum(Order)
            post_command_id = fields.String()
            affiche_options = fields.Dict()

        try:
            result = PatchRefreshJobSchema().load(request.json)
        except ValidationError as error:
            return error.messages, 400

        try:
            job = modify_refresh_job(app.config['DB_PATH'], job, result.get('identifier'), result.get('display_name'),
                                     result.get('hostname'), result.get('schedule'), result.get('enabled'), result.get('filter'),
                                     result.get('order'), result.get('affiche_options'), result.get('post_command_id'))
            app.logger.info(f'Modified refresh job "{identifier}"')
            return refresh_job_to_dict(job), 200
        except Exception as error:
            app.logger.debug('Invalid arguments', exc_info=True)
            return getattr(error, 'message', str(error)), 400


@app.route('/schema/collection.json')
def schema_collection():
    json_schema = JSONSchema(props_ordered=True)
    return json_schema.dump(CollectionSchema())


@app.route('/schema/<class_name>/settings.json')
def schema_collection_settings(class_name: str):
    schema = get_collection_settings_schema(class_name)
    if schema is None:
        return 'Unknown collection class', 400

    json_schema = JSONSchema(props_ordered=True)
    return json_schema.dump(schema)


@app.route('/schema/schedule.json')
def schema_refresh_job():
    json_schema = JSONSchema(props_ordered=True)
    return json_schema.dump(RefreshJobSchema_MarshmallowJsonSchemaCompatibility())


@app.route('/default/schedule.json')
def default_refresh_job():
    return RefreshJobSchema().load({
        'identifier': 'local',
        'hostname': 'localhost',
        'schedule': '*/15 * * * *'
    })


@app.route('/default/collection.json')
def default_collection():
    return CollectionSchema().load({
        'identifier': 'local',
        'schedule': '0 */1 * * *',
        'class_name': FileSystemCollection.__name__,
        'settings': FileSystemCollection.get_settings_default()
    })
