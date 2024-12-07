venv=".venv/bin/activate"
if [ -e "$venv" ]; then
    . "$venv"
fi

Host=0.0.0.0
Port=80
Config=

while getopts "h::p::c::" option; do
   case $option in
      h)
         Host=$OPTARG;;
      p)
         Port=$OPTARG;;
      c)
         Config=$OPTARG;;
     \?)
         echo "invalid option"
         exit;;
   esac
done

if [ -n "$Config" ]; then
    export AFFICHE_CONFIG_PATH="$Config"
fi

rm nohup.out
nohup flask run --host=$Host --port=$Port &
