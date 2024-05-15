import logging
import signal
import subprocess
import json
import random
import threading
from enum import Enum
from pathlib import Path, PurePosixPath
from logging.config import dictConfig
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen, urlretrieve

from flask import Flask, request, redirect, send_file, url_for
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


DisplayWriterStatus = Enum('DisplayWriterStatus', ['READY', 'FAILED', 'BUSY'])
DisplayWriterSubStatus = Enum('DisplayWriterSubStatus', ['NONE', 'LAUNCHING', 'CONVERTING', 'DISPLAYING'])
display_writer_last_status = DisplayWriterStatus.READY
display_writer_last_sub_status = DisplayWriterSubStatus.NONE

display_writer_last_preview: Path = None
display_writer_preview_lock = threading.Lock()

def update_display_writer_preview(preview_path: Path):
    global display_writer_last_preview

    try:
        if not preview_path.exists():
            return

        with display_writer_preview_lock:
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

def run_display_writer(command: list[Path | str], image_path: Path, preview_path: Path, options: dict[str]) -> bool:
    global display_writer_last_status

    if display_writer_last_status == DisplayWriterStatus.BUSY:
        return False

    def run():
        global display_writer_last_status
        global display_writer_last_sub_status

        try:
            options_string = json.dumps(options)
            process = subprocess.Popen([*command, image_path, '--options', options_string, '--preview', preview_path],
                                        stdout=subprocess.PIPE, universal_newlines=True, bufsize=1)

            display_writer_last_status = DisplayWriterStatus.BUSY
            display_writer_last_sub_status = DisplayWriterSubStatus.LAUNCHING
            while True:
                output_line = process.stdout.readline()
                if output_line.startswith('Status: '):
                    status_string = output_line.split()[-1]
                    try:
                        display_writer_last_sub_status = DisplayWriterSubStatus[status_string]
                    except Exception:
                        pass

                if display_writer_last_sub_status == DisplayWriterSubStatus.DISPLAYING:
                    update_display_writer_preview(preview_path)

                exit_code = process.poll()
                if exit_code is not None:
                    break

            display_writer_last_status = DisplayWriterStatus.READY if \
                exit_code == 0 else DisplayWriterStatus.FAILED
            display_writer_last_sub_status = DisplayWriterSubStatus.NONE
        except Exception:
            display_writer_last_status = DisplayWriterStatus.FAILED
            affiche_logger.exception('Failed to refresh display')
            process.kill()
        finally:
            display_writer_last_sub_status = DisplayWriterSubStatus.NONE
            update_display_writer_preview(preview_path)
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
    global display_writer_last_status

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
            value = request.form.get(name, type=type)
            if value is not None:
                options[name] = value
        except ValueError:
            pass

    display_writer_command: list[Path | str] = app.config['DISPLAY_WRITER_COMMAND']
    preview_path: Path = app.config['PREVIEW_PATH'] / f'preview_{job_id}.png'
    if not run_display_writer(display_writer_command, file_path, preview_path, options):
        return redirect(request.url)

    return redirect(request.url)

@app.route('/status')
def status():
    global display_writer_last_status
    global display_writer_last_sub_status
    global display_writer_last_preview

    response = {
        'status': display_writer_last_status.name,
        'subStatus': display_writer_last_sub_status.name
    }

    with display_writer_preview_lock:
        if display_writer_last_preview:
            response['preview'] = url_for('preview', file_name=display_writer_last_preview.name)

    return response, 200

@app.route('/preview/<file_name>')
def preview(file_name: str):
    global display_writer_last_preview

    with display_writer_preview_lock:
        if not display_writer_last_preview or display_writer_last_preview.name != file_name:
            return '', 204

        try:
            if display_writer_last_preview.exists():
                return send_file(display_writer_last_preview)
        except Exception as exception:
            app.log_exception(exception)

        return '', 204

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
