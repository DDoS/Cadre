import logging
import signal
import subprocess
import json
import random
import threading
from enum import Enum
from pathlib import Path, PurePosixPath
from datetime import date, datetime, timedelta, timezone
from logging.config import dictConfig
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen, urlretrieve
from typing import Any

from flask import Flask, Response, request, redirect, send_file, stream_with_context, url_for
from werkzeug.utils import secure_filename
import requests


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


affiche_logger = logging.getLogger('affiche')


cru_available = False
try:
    import sys
    sys.path.append(str(Path(__file__).absolute().parent.parent / 'cru/build/release'))
    import cru
    cru_available = True
except ModuleNotFoundError:
    affiche_logger.error('cru module not found: image metadata will not be available.')


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


def setup_app_config(app: Flask):
    app.config.from_file('default_config.json', load=json.load)
    app.config.from_file('config.json', load=json.load, silent=True)

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

def update_display_writer_preview_locked(preview_path: Path):
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
        if preview_path is not None:
            preview_path.unlink(missing_ok=True)

def try_load_image_info(path: Path) -> dict[str, Any] | None:
    if not cru_available:
        return None

    try:
        data = cru.load_image_info(str(path))
        if not data:
            return None

        fields = {}

        if data.times.original:
            capture_date = datetime.fromtimestamp(data.times.original.seconds, timezone.utc)
            capture_date = capture_date.astimezone(timezone(timedelta(seconds=data.times.original.offset)))
            fields['captureDateTime'] = capture_date.isoformat()
        if data.times.gps:
            if data.times.gps.date_only:
                fields['gpsDate'] = date.fromtimestamp(data.times.gps.seconds).isoformat()
            else:
                fields['gpsDateTime'] = datetime.fromtimestamp(data.times.gps.seconds, timezone.utc).isoformat()

        if data.make_and_model.camera:
            fields['cameraMakeAndModel'] = data.make_and_model.camera
        if data.make_and_model.lens:
            fields['lensMakeAndModel'] = data.make_and_model.lens

        if data.camera_settings.aperture:
            fields['apertureSetting'] = data.camera_settings.aperture
        if data.camera_settings.exposure:
            fields['exposureSetting'] = data.camera_settings.exposure
        if data.camera_settings.iso:
            fields['isoSetting'] = data.camera_settings.iso
        if data.camera_settings.focal_length:
            fields['focalLengthSetting'] = data.camera_settings.focal_length

        if data.gps.longitude:
            fields['gpsLongitude'] = data.gps.longitude
        if data.gps.latitude:
            fields['gpsLatitude'] = data.gps.latitude
        if data.gps.altitude:
            fields['gpsAltitude'] = data.gps.altitude
        if data.gps.speed:
            fields['gpsSpeed'] = data.gps.speed
        if data.gps.direction:
            fields['gpsDirection'] = data.gps.direction
        fields['gpsZeroDirection'] = data.gps.zero_direction.name

        return fields
    except Exception:
        return None

def run_display_writer(command: list[Path | str], image_path: Path, preview_path: Path,
                       options: dict[str], info: dict[str]) -> bool:
    global display_writer_last_status

    if display_writer_last_status == DisplayWriterStatus.BUSY:
        return False

    def run():
        global display_writer_last_status
        global display_writer_last_sub_status
        global display_writer_image_info

        try:
            options_string = json.dumps(options)
            process = subprocess.Popen([*command, image_path, '--options', options_string, '--preview', preview_path],
                                        stdout=subprocess.PIPE, universal_newlines=True, bufsize=1)

            with display_writer_update_lock:
                display_writer_last_status = DisplayWriterStatus.BUSY
                display_writer_last_sub_status = DisplayWriterSubStatus.LAUNCHING
                display_writer_update_lock.notify_all()

            image_info = try_load_image_info(image_path)
            if image_info is not None:
                image_info.update(info)

            while True:
                output_line = process.stdout.readline()
                if output_line.startswith('Status: '):
                    status_string = output_line.split()[-1]
                    try:
                        with display_writer_update_lock:
                            display_writer_last_sub_status = DisplayWriterSubStatus[status_string]
                            if display_writer_last_sub_status == DisplayWriterSubStatus.DISPLAYING:
                                display_writer_image_info = image_info
                                update_display_writer_preview_locked(preview_path)
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
                display_writer_image_info = image_info
                update_display_writer_preview_locked(preview_path)
                display_writer_update_lock.notify_all()
        except Exception:
            with display_writer_update_lock:
                display_writer_last_status = DisplayWriterStatus.FAILED
                display_writer_last_sub_status = DisplayWriterSubStatus.NONE
                display_writer_image_info = None
                update_display_writer_preview_locked(preview_path)
                display_writer_update_lock.notify_all()
            affiche_logger.exception('Failed to refresh display')
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
    for name, type in [('rotation', str), ('dynamic_range', float), ('exposure', float),
                       ('brightness', float), ('contrast', float), ('sharpening', float),
                       ('clipped_chroma_recovery', float), ('error_attenuation', float)]:
        try:
            value = request.form.get(f'options.{name}', type=type)
            if value is not None:
                options[name] = value
        except ValueError:
            pass

    info = {}
    for name, type in [('path', str), ('collection', str)]:
        try:
            value = request.form.get(f'info.{name}', type=type)
            if value is not None:
                info[name] = value
        except ValueError:
            pass

    display_writer_command: list[Path | str] = app.config['DISPLAY_WRITER_COMMAND']
    preview_path: Path = app.config['PREVIEW_PATH'] / f'preview_{job_id}.png'
    if not run_display_writer(display_writer_command, file_path, preview_path, options, info):
        return redirect(request.url)

    return redirect(request.url)

@app.route('/status')
def status():
    def get_event_data(wait: bool = True):
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

            return f'data: {json.dumps(data)}\n\n'

    @stream_with_context
    def event_generator():
        yield get_event_data(False)

        try:
            while True:
                yield get_event_data()
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
