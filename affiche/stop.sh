Port=80
while getopts "p::" option; do
   case $option in
      p)
         Port=$OPTARG;;
     \?)
         echo "invalid option"
         exit;;
   esac
done

pid=$(lsof -i :$Port | awk '/flask|Python/ { pid=$2 } END { print pid }')
if [ -n "$pid" ]; then
    kill -2 "$pid"
    echo "Sent SIGINT to $pid"
fi
