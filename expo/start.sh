venv=".venv/bin/activate"
if [ -e "$venv" ]; then
    . "$venv"
fi

rm nohup.out
nohup flask run --host=0.0.0.0 --port=21110 &
