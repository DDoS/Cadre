pid=$(lsof -i :21110 | awk '/flask|Python/ { pid=$2 } END { print pid }')
if [ -n "$pid" ]; then
    kill -2 "$pid"
    echo "Sent SIGINT to $pid"
fi
