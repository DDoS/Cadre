from pathlib import Path
import subprocess
from enum import Enum
import json
import random
import threading
import traceback
from logging.config import dictConfig

from flask import Flask, request, redirect, send_file, url_for
from werkzeug.utils import secure_filename

SERVER_PATH = Path(__file__).parent
TEMP_PATH = SERVER_PATH / 'temp'
TEMP_PATH.mkdir(exist_ok=True)

dictConfig({
    'version': 1,
    'handlers': {
        'file.handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(TEMP_PATH / 'app.log'),
            'maxBytes': 10_000_000,
            'backupCount': 2,
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'werkzeug': {
            'level': 'DEBUG',
            'handlers': ['file.handler'],
        },
    },
})

def delete_all_files(directory: Path):
    [file.unlink() for file in directory.iterdir() if file.is_file()]

UPLOAD_PATH = TEMP_PATH / 'upload'
UPLOAD_PATH.mkdir(exist_ok=True)
delete_all_files(UPLOAD_PATH)

PREVIEW_PATH = TEMP_PATH / 'preview'
PREVIEW_PATH.mkdir(exist_ok=True)
delete_all_files(PREVIEW_PATH)

DISPLAY_WRITER_PATH = SERVER_PATH.parent / 'encre/misc/write_to_display.py'
if not DISPLAY_WRITER_PATH.is_file():
    raise Exception(f'File not found: "{DISPLAY_WRITER_PATH}"')


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
        traceback.print_exc()
        if preview_path is not None:
            preview_path.unlink(missing_ok=True)

def run_display_writer(exec_path: Path, image_path: Path, preview_path: Path, options: dict[str]) -> bool:
    global display_writer_last_status

    if display_writer_last_status == DisplayWriterStatus.BUSY:
        return False

    def run():
        global display_writer_last_status
        global display_writer_last_sub_status

        try:
            options_string = json.dumps(options)
            process = subprocess.Popen(['python3', '-u', exec_path, image_path,
                                        '--preview', preview_path, '--options', options_string, '--status'],
                                        stdout=subprocess.PIPE, universal_newlines=True, bufsize=1)

            display_writer_last_status = DisplayWriterStatus.BUSY
            display_writer_last_sub_status = DisplayWriterSubStatus.LAUNCHING
            while True:
                output_line = process.stdout.readline()
                if output_line.startswith('Status: '):
                    status_string = output_line.split()[-1]
                    try:
                        display_writer_last_sub_status = DisplayWriterSubStatus[status_string]
                    except:
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
            traceback.print_exc()
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


def random_string() -> str:
    return '%030x' % random.randrange(16**30)


app = Flask(__name__)
app.config['UPLOAD_PATH'] = UPLOAD_PATH
app.config['PREVIEW_PATH'] = PREVIEW_PATH
app.config['DISPLAY_WRITER_PATH'] = DISPLAY_WRITER_PATH
app.secret_key = random_string()

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global display_writer_last_status

    if request.method == 'GET':
        return app.send_static_file('index.html')

    file = request.files.get('file')
    if not file:
        return redirect(request.url)

    if display_writer_last_status == DisplayWriterStatus.BUSY:
        return redirect(request.url)

    job_id = random_string()

    exec_path: Path = app.config['DISPLAY_WRITER_PATH']

    file_name = Path(secure_filename(file.filename))
    file_name = file_name.with_stem(f'{file_name.stem}_{job_id}')
    file_path = app.config['UPLOAD_PATH'] / file_name
    file.save(file_path)

    preview_path: Path = app.config['PREVIEW_PATH'] / f'preview_{job_id}.png'

    options = {}
    for name, type in [('rotation', str), ('dynamic_range', float), ('exposure', float),
                       ('brightness', float), ('contrast', float), ('sharpening', float),
                       ('clipped_chroma_recovery', float)]:
        try:
            value = request.form.get(name, type=type)
            if value is not None:
                options[name] = value
        except ValueError:
            pass

    if not run_display_writer(exec_path, file_path, preview_path, options):
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
