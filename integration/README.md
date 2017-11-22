Integration Testing
===================

Goal: on every docker image build, download the corresponding image and run a quick integration test.

Requirements
------------
- python3.6
- jq
- docker

Optional: a slack channel setup for notifications.

Quick cloud-init / User Data for Centos-7:
```
#cloud-config
locale: en_US.UTF-8
timezone: UTC
packages:
  - vim
runcmd:
  - yum install -y epel-release yum-utils
  - yum install -y device-mapper-persistent-data lvm2 s3cmd
  - yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  - yum install -y docker-ce
  - systemctl start docker
  - usermod -aG docker centos
```

Install
-------
Setup a systemd daemon to run the python server that listens to docker hub's webhook:
```
echo {
[Unit]
Description=Dockerhub on build listener to pull and test
Requires=network-online.target
After=network-online.target

[Service]
User=centos
KillSignal=SIGINT
Restart=on-failure
ExecStart=/usr/bin/python3.6 /home/centos/integration/dockerhub_wh_listener.py

[Install]
WantedBy=multi-user.target
} > /etc/systemd/system/dockerhub_wh.service

sudo systemctl daemon-reload
sudo systemctl start dockerhub_wh
```

Create an onbuild.sh exeutable bash script.
Setup a Slack hook to post notification to a channel.
The value of that secret is stored on the server in the file `.env` as that environment variable `SLACK_URL`

For example:
```
# /home/centos/integration/.env
SLACK_URL="https://hooks.slack.com/services/123secret
```

Optional: setup HAProxy
-----------------------
```
# on centos-7 SELinux is preventing haproxy to connect to the backends:
sudo setsebool -P haproxy_connect_any on
```