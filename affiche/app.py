import logging
import os
import signal
import subprocess
import json
import random
import threading
import sys
from enum import Enum
from pathlib import Path, PurePosixPath
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from logging.config import dictConfig
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen, urlretrieve
from typing import Any

from flask import Flask, Response, request, redirect, send_file, stream_with_context, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from marshmallow import Schema, fields
import requests

sys.path.append(str(Path(__file__).absolute().parent.parent / 'cru'))
import cru_utils


# Make sure we can shutdown using SIGINT
if signal.getsignal(signal.SIGINT) == signal.SIG_IGN:
    signal.signal(signal.SIGINT, signal.default_int_handler)


# socket.getfqdn is broken on macOS, but platform.node() should return the correct value
def get_external_hostname():
    import platform
    if platform.system() == 'Darwin':
        return platform.node()

    import socket
    return socket.getfqdn()


SERVER_PATH = Path(__file__).parent

dictConfig({
    'version': 1,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(process)d %(name)s: %(message)s'
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
        'affiche': {
            'level': 'INFO',
            'handlers': ['file.handler']
        },
        'werkzeug': {
            'level': 'INFO',
            'handlers': ['file.handler']
        }
    }
})


affiche_logger = logging.getLogger('affiche')


if not cru_utils.available:
    affiche_logger.error('cru module not found: image info will not be available.')


@dataclass
class Option:
    type: type
    default: Any

class OptionType(Enum):
    BOOLEAN = 'boolean'
    NUMBER = 'number'
    INTEGER = 'integer'
    STRING = 'string'

class OptionSchema(Schema):
    display_name = fields.String(required=True)
    type = fields.Enum(OptionType, by_value=True, required=True)
    enum = fields.Dict(fields.String, fields.String)
    default = fields.Raw(load_default=None)
    placeholder = fields.String(load_default=None)

def display_writer_parse_options(options_schema_json: dict[str, Any], options_json: dict[str, Any]):
    OptionsSchema = Schema.from_dict(
        {key: fields.Nested(OptionSchema) for key in options_schema_json})
    options_schema = OptionsSchema().load(options_schema_json)

    type_and_default: dict[str, Option] = {}
    json_properties: dict[str, dict[str, Any]] = {}
    order = 0
    for name, option_schema in options_schema.items():
        match option_schema['type']:
            case OptionType.BOOLEAN:
                Type = bool
            case OptionType.NUMBER:
                Type = float
            case OptionType.INTEGER:
                Type = int
            case OptionType.STRING:
                Type = str
            case _:
                raise ValueError()
        default = option_schema['default']
        if default is not None:
            default = Type(default)
        type_and_default[name] = Option(Type, default)

        property_options = {}
        property = {
            'title': option_schema['display_name'],
            'type': option_schema['type'].value,
            'propertyOrder': order,
            'options': property_options
        }

        if 'placeholder' in option_schema:
            property_options['inputAttributes'] = {
                'placeholder': option_schema['placeholder']
            }

        if 'enum' in option_schema:
            enum = option_schema['enum']
            property['enum'] = list(enum.keys())
            property_options['enum_titles'] = list(enum.values())

        json_properties[name] = property
        order += 1

    for name, option_default in options_json.items():
        if name not in type_and_default:
            raise KeyError(f'Option {name} is not in the schema')

        option = type_and_default[name]
        option.default = option.type(option_default)

    json_schema = {
        'type': 'object',
        'properties': json_properties,
        'additionalProperties': False
    }

    return json_schema, type_and_default


def setup_app_config(app: Flask):
    app.config.from_file('default_config.json', load=json.load)

    config_path = os.environ.get('AFFICHE_CONFIG_PATH', 'config.json')
    app.config.from_file(config_path, load=json.load, silent=True)

    def delete_all_files(directory: Path):
        [file.unlink() for file in directory.iterdir() if file.is_file()]

    temp_path: Path = SERVER_PATH / app.config['TEMP_PATH']
    temp_path.mkdir(exist_ok=True)
    app.config['TEMP_PATH'] = temp_path

    upload_path = temp_path / 'upload'
    upload_path.mkdir(exist_ok=True)
    delete_all_files(upload_path)
    app.config['UPLOAD_PATH'] = upload_path

    preview_path = temp_path / 'preview'
    preview_path.mkdir(exist_ok=True)
    delete_all_files(preview_path)
    app.config['PREVIEW_PATH'] = preview_path

    display_writer_path: Path = SERVER_PATH / app.config['DISPLAY_WRITER_COMMAND'][0]
    if not display_writer_path.is_file():
        raise Exception(f'Display writer executable not found: "{display_writer_path}"')
    app.config['DISPLAY_WRITER_COMMAND'][0] = display_writer_path

    display_writer_options_schema_path: Path = SERVER_PATH / app.config['DISPLAY_WRITER_OPTIONS_SCHEMA_PATH']
    if not display_writer_options_schema_path.is_file():
        raise Exception(f'Display writer options schema not found: "{display_writer_options_schema_path}"')

    display_writer_options = app.config['DISPLAY_WRITER_OPTIONS']

    with open(display_writer_options_schema_path) as display_writer_options_schema_file:
        display_writer_options_schema = json.load(display_writer_options_schema_file)
        app.config['DISPLAY_WRITER_OPTIONS_SCHEMA'], app.config['DISPLAY_WRITER_OPTIONS']= \
                display_writer_parse_options(display_writer_options_schema, display_writer_options)

    expo_address = app.config['EXPO_ADDRESS']
    if expo_address is not None:
        if expo_address == '':
            expo_address = get_external_hostname()
        if ':' not in expo_address:
            expo_address += ':21110'
        app.config['EXPO_ADDRESS'] = expo_address


display_writer_update_lock = threading.Condition()
DisplayWriterStatus = Enum('DisplayWriterStatus', ['READY', 'FAILED', 'BUSY'])
DisplayWriterSubStatus = Enum('DisplayWriterSubStatus', ['NONE', 'LAUNCHING', 'CONVERTING', 'DISPLAYING'])
display_writer_last_status = DisplayWriterStatus.READY
display_writer_last_sub_status = DisplayWriterSubStatus.NONE
display_writer_image_info: dict[str, Any] | None = None
display_writer_last_preview: Path | None = None

def run_display_writer(command: list[Path | str], image_path: Path, preview_path: Path,
                       options: dict[str], info: dict[str, Any]) -> bool:
    global display_writer_last_status

    if display_writer_last_status == DisplayWriterStatus.BUSY:
        return False

    def update_preview_locked():
        global display_writer_last_preview

        try:
            if not preview_path.exists():
                return

            if display_writer_last_preview is not None:
                if display_writer_last_preview.samefile(preview_path):
                    return

                display_writer_last_preview.unlink(missing_ok=True)
                display_writer_last_preview = None

            display_writer_last_preview = preview_path
        except Exception:
            affiche_logger.exception('Failed to update preview')
            preview_path.unlink(missing_ok=True)

    def run():
        global display_writer_last_status
        global display_writer_last_sub_status
        global display_writer_image_info

        process = None
        try:
            if image_info := cru_utils.get_image_info_dict(image_path):
                info.update(image_info)

            full_command = [*command, image_path, '--options', json.dumps(options),
                            '--info', json.dumps(info), '--preview', preview_path]
            process = subprocess.Popen(full_command, stdout=subprocess.PIPE,
                                       universal_newlines=True, bufsize=1)

            with display_writer_update_lock:
                display_writer_last_status = DisplayWriterStatus.BUSY
                display_writer_last_sub_status = DisplayWriterSubStatus.LAUNCHING
                display_writer_update_lock.notify_all()

            while True:
                output_line = process.stdout.readline()
                if output_line.startswith('Status: '):
                    status_string = output_line.split()[-1]
                    try:
                        with display_writer_update_lock:
                            display_writer_last_sub_status = DisplayWriterSubStatus[status_string]
                            if display_writer_last_sub_status == DisplayWriterSubStatus.DISPLAYING:
                                display_writer_image_info = info
                                update_preview_locked()
                            display_writer_update_lock.notify_all()
                    except Exception:
                        pass

                exit_code = process.poll()
                if exit_code is not None:
                    break

            with display_writer_update_lock:
                display_writer_last_status = DisplayWriterStatus.READY if \
                    exit_code == 0 else DisplayWriterStatus.FAILED
                display_writer_last_sub_status = DisplayWriterSubStatus.NONE
                display_writer_image_info = info
                update_preview_locked()
                display_writer_update_lock.notify_all()
        except Exception:
            with display_writer_update_lock:
                display_writer_last_status = DisplayWriterStatus.FAILED
                display_writer_last_sub_status = DisplayWriterSubStatus.NONE
                display_writer_image_info = None
                update_preview_locked()
                display_writer_update_lock.notify_all()
            affiche_logger.exception('Failed to refresh display')
            if process:
                process.kill()
        finally:
            image_path.unlink(missing_ok=True)

    try:
        threading.Thread(target=run, daemon=True).start()
        return True
    except Exception as exception:
        app.log_exception(exception)
        image_path.unlink(missing_ok=True)
        return False


def file_name_from_url(url: str, fallback: str) -> str:
    file_path: None | PurePosixPath = None
    with urlopen(url) as response:
        if filename := response.headers.get_filename():
            file_path = PurePosixPath(filename)

    if not file_path:
        url_path = PurePosixPath(unquote(urlsplit(url).path))
        if url_path.suffix:
            file_path = url_path

    if not file_path:
        file_path = PurePosixPath(fallback)

    return file_path.name


def random_string() -> str:
    return '%030x' % random.randrange(16**30)


app = Flask(__name__)
app.json.sort_keys = False
app.json.include_nulls = True
CORS(app)
setup_app_config(app)
app.secret_key = random_string()

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return app.send_static_file('index.html')

    file = request.files.get('file')
    url = request.form.get('url', type=str)
    if not file and not url:
        return redirect(request.url)

    if display_writer_last_status == DisplayWriterStatus.BUSY:
        return redirect(request.url)

    job_id = random_string()

    if file:
        file_name = Path(secure_filename(file.filename))
        app.logger.info(f'Received image "{file_name}"')
        file_name = file_name.with_stem(f'{file_name.stem}_{job_id}')
        file_path = app.config['UPLOAD_PATH'] / file_name
        file.save(file_path)
    else:
        try:
            file_name = Path(file_name_from_url(url, 'url_image'))
            app.logger.info(f'Received image "{file_name}"')
            file_name.with_stem(f'{file_name.stem}_{job_id}')
            file_path = app.config['UPLOAD_PATH'] / file_name
            urlretrieve(url, file_path)
        except Exception:
            app.logger.debug(f'Failed to download image from "{url}" to "{file_path}"')
            return 'Failed to retrieve the file from the URL', 400

    options = {}
    for name, option in app.config['DISPLAY_WRITER_OPTIONS'].items():
        try:
            value = request.form.get(f'options.{name}', type=option.type)
            if value is None:
                # Alternate notation mandated by jsoneditor.js
                value = request.form.get(f'options[{name}]', type=option.type)
            if value is None:
                value = option.default
            if value is not None:
                options[name] = value
        except ValueError:
            pass

    info = {}
    if info_json := request.form.get('info', type=str):
        try:
            info = json.loads(info_json)
        except json.JSONDecodeError:
            pass

    display_writer_command: list[Path | str] = app.config['DISPLAY_WRITER_COMMAND']
    preview_path = app.config['PREVIEW_PATH'] / f'preview_{job_id}.png'
    if not run_display_writer(display_writer_command, file_path, preview_path, options, info):
        return redirect(request.url)

    return redirect(request.url)

@app.route('/display_writer_options_schema.json')
def display_writer_options_schema():
    return app.config['DISPLAY_WRITER_OPTIONS_SCHEMA'], 200

@app.route('/display_writer_options_defaults.json')
def display_writer_options_defaults():
    return {name: option.default for name, option in
            app.config['DISPLAY_WRITER_OPTIONS'].items()}, 200

def get_status_data(wait: bool = False):
    with display_writer_update_lock:
        if wait:
            display_writer_update_lock.wait(2 * 60)

        data = {
            'status': display_writer_last_status.name,
            'subStatus': display_writer_last_sub_status.name
        }
        data['preview'] = url_for('preview', file_name=display_writer_last_preview.name) if \
                        display_writer_last_preview else None
        data['imageInfo'] = display_writer_image_info if display_writer_image_info else None
        return data

@app.route('/status')
def status():
    return get_status_data(), 200

@app.route('/status/stream')
def status_stream():
    def get_event_data(wait: bool):
        return f'data: {json.dumps(get_status_data(wait))}\n\n'

    @stream_with_context
    def event_generator():
        yield get_event_data(False)

        try:
            while True:
                yield get_event_data(True)
        except GeneratorExit:
            app.logger.debug('Client disconnected')

    return Response(event_generator(), mimetype='text/event-stream')

@app.route('/preview/<file_name>')
def preview(file_name: str):
    with display_writer_update_lock:
        if not display_writer_last_preview or display_writer_last_preview.name != file_name:
            return '', 204

        try:
            if display_writer_last_preview.exists():
                return send_file(display_writer_last_preview)
        except Exception as exception:
            app.log_exception(exception)

        return '', 204

@app.route('/map_tiles')
def map():
    return app.config['MAP_TILES'], 200

@app.route('/expo')
def expo():
    expo_address = app.config['EXPO_ADDRESS']
    if not expo_address:
        return '', 204

    try:
        response = requests.get(f'http://{expo_address}/schedules?hostname={get_external_hostname()}')
        schedules = {}
        for schedule in response.json():
            if schedule['enabled']:
                schedules[schedule['identifier']] = schedule['display_name']
    except Exception as exception:
        app.logger.debug('Expo error', exc_info=True)
        return f'Expo error: {getattr(exception, "message", str(exception))}', 503

    return {
        'address': expo_address,
        'schedules': schedules
    }, 200
