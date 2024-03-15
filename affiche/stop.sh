pid=$(sudo lsof -i :80 | awk '/flask/ { pid=$2 } END { print pid }')
if [ -n "$pid" ]; then
    kill "$pid"
    echo "killed $pid"
fi
