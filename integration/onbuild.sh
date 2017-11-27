#!/bin/bash

# Send notifications to a slack channel
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
    prune_stdout=$(docker image prune --force || true)
    codeblock="\`\`\`"
    cmd_integ_test="docker run --rm --net host --tmpfs /tmp -e PROM_TEXT=/tmp/metrics.prom hmalphettes/s3-storage-analyser:$2 s3_storage_analyser --unit KB --conc 6"
    if res2=$($cmd_integ_test 2>&1); then
      notify "Integration test of hmalphettes/s3-storage-analyser:
$codeblock
docker pull hmalphettes/s3-storage-analyser:$2
$pull_stdout
docker image prune
$prune_stdout
$codeblock

Integration test:
$codeblock
$cmd_integ_test
$res2
$codeblock
"
      if [ "$2" = "latest" ]; then
        docker rm --force s3analyser_endpoint
        docker run --name s3analyser_endpoint -e TOKEN="$TOKEN" \
          --tmpfs /tmp -e PROM_TEXT=/tmp/metrics.prom \
          --net host -d hmalphettes/s3-storage-analyser server --restart=on-failure
      fi
    else
      notify "Integration test failed. Please ssh in the server and run \"journalctl -xfeu dockerhub_wh\":
$codeblock
$cmd_integ_test
$res2
$codeblock
"
    fi
fi