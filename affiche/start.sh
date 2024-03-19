venv=".venv/bin/activate"
if [ -e "$venv" ]; then
    . "$venv"
fi

flask run --host=0.0.0.0 --port=80 &
tail -F temp/app.log
