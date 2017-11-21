"""Python server that processes docker hub webhook call when a build
of hmalphettes/s3-storage-analyser is completed"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from pprint import pprint
import subprocess
import os
import json

class RequestHandler(BaseHTTPRequestHandler):
    """Server for handlng docker hub webhook"""
    def do_POST(self):
        """
        Expect a JSON payload of the format described here:
        https://docs.docker.com/docker-hub/webhooks/

        ::
            {
                "push_data": {
                    "pushed_at": 1511235401,
                    "images": [],
                    "tag": "latest",
                    "pusher": "hmalphettes"
                },
                "repository": {
                    "repo_name": "hmalphettes/s3-storage-analyser"
                }
            }

        Extract repo_name and tag, runs docker pull repo_name/tag
        Then run a command as configured.
        Note we ignore the repo_name and hardcode our repo: hmalphettes/s3-storage-analyser
        for obvious security reasons
        """
        content_len = int(self.headers['content-length'])
        post_body = self.rfile.read(content_len)
        data = json.loads(post_body)

        try:
            tag = data['push_data']['tag']
            repo_name = data['repository']['repo_name']
            if repo_name != 'test':
                # Security: Dont allow our service to be used for any kind of docker images!
                repo_name = 'hmalphettes/s3-storage-analyser'
            out = _run_cmd(repo_name, tag)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(out)
        except subprocess.CalledProcessError as err:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(err.__str__())
        return

def _run_cmd(repo_name, tag):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    full_cmd = f'{script_dir}/onbuild.sh {repo_name} {tag}'
    return subprocess.check_output(
        full_cmd.split(' '),
        stderr=subprocess.STDOUT,
        shell=True,
        executable='/bin/bash')

if __name__ == '__main__':
    SERVER = HTTPServer(('localhost', 8000), RequestHandler)
    print('Starting server at http://localhost:8000')
    SERVER.serve_forever()
