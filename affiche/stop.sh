pid=$(lsof -i :80 | awk '/flask|Python/ { pid=$2 } END { print pid }')
if [ -n "$pid" ]; then
    kill -2 "$pid"
    echo "Sent SIGINT to $pid"
fi
