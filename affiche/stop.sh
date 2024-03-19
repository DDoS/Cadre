pid=$(lsof -i :80 | awk '/flask|Python/ { pid=$2 } END { print pid }')
if [ -n "$pid" ]; then
    kill -6 "$pid"
    echo "Stopped $pid"
fi
