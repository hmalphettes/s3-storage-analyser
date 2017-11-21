#!/bin/bash

# slck notifications
notify() {
  if [ -z "$SLACK_URL" ]; then
    local d; d="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    set -a;
    . "$d/.env"
  fi
  [ -z "$SLACK_URL" ] && echo "ERROR: the SLACK_URL env var is missing. Notifications disabled" && return
  local msg; msg="$(jq -n -c -M --arg var "${1:?}" '$var')"
  local attachs=""
  [ -n "$2" ] && attachs=",\"attachments\":[{\"text\":$(jq -n -c -M --arg var "$2" '$var')}]"
  curl -sf -X POST -H 'Content-type: application/json' --data "{\"text\":$msg,\"mrkdwn\":true,\"username\":\"Bot s3analyser.huguesm.name\"$attachs}" "$SLACK_URL"
}

if [ "$1" = "test" ]; then
    echo "Hello $2"
elif [ -n "$2" ]; then
    set -e
    # Hardcode the repository because this service is opened to the world
    # and we certainly dont want to let any image have a run on our server.
    pull_stdout=$(docker pull "hmalphettes/s3-storage-analyser:$2")
    if res2=$(docker run --rm --net host "hmalphettes/s3-storage-analyser:$2" --unit KB --pool-size 8 --prefix 's3://hm.samples'); then
      notify "Pulling: hmalphettes/s3-storage-analyser:$2 and Integration test:"'```'"$pull_stdout""$res2"'```'
    else
      notify 'Integration test failed. Please ssh in the server and run "journalctl -xfeu dockerhub_wh"'
    fi
fi
