"""Python server that processes docker hub webhook call when a build
of hmalphettes/s3-storage-analyser is completed"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from pprint import pprint
from traceback import print_exception
import subprocess
import threading
import os
import json

# Simple global rate limit:
# Run a single onbuild at a time
LOCK_ONBUILD = threading.Lock()

class RequestHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def do_GET(self):
        if 'ico' in self.path:
            self.send_response(404)
            self.end_headers()
            return

        token = os.environ['TOKEN'] or 's3cr3t'

        query_components = {'token': None}
        query = urlparse(self.path).query
        if query:
            query_components.update(dict(qc.split("=") for qc in query.split('&')))

        if query_components['token'] != token:
            # redirect to github if the token is missing
            self.send_response(302)
            self.send_header('Location', 'https://github.com/hmalphettes/s3-storage-analyser')
            self.end_headers()
            self.wfile.write(b'Redirecting to https://github.com/hmalphettes/s3-storage-analyser\n')
            return

        self.wfile.write(b'Welcome to the dockerhub hook listener for s3-storage-analyser')

    """Server for handling docker hub webhook"""
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

        try:
            data = json.loads(post_body)
            tag = data['push_data']['tag']
            repo_name = data['repository']['repo_name']
            if repo_name != 'test':
                # Security: Dont allow our service to be used for any kind of docker images!
                repo_name = 'hmalphettes/s3-storage-analyser'
            out = _run_onbuild(repo_name, tag)
            print(out)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(out)
        except json.decoder.JSONDecodeError as err:
            print(f'Unable to parse {post_body}')
            self.send_response(500)
            self.end_headers()
            self.wfile.write(err.__str__())
        except subprocess.CalledProcessError as err:
            msg = f'{err.__str__()} {err.output}'
            print(f'Subprocess Error {msg}')
            self.send_response(500)
            self.end_headers()
            self.wfile.write(msg.encode())
        except Exception as err:
            print(f'Error {err.__str__()}')
            self.send_response(500)
            self.end_headers()
            self.wfile.write(err.__str__().encode())
        return

def _run_onbuild(repo_name, tag):
    if not LOCK_ONBUILD.acquire(False):
        print('There is already an onbuild running')
        raise ValueError('There is already an onbuild running')
    try:
        script_dir = os.path.dirname(os.path.realpath(__file__))
        full_cmd = f'bash {script_dir}/onbuild.sh {repo_name} {tag}'
        print(f'Entered RUNNING_ONBUILD {full_cmd}')
        return subprocess.check_output(
            full_cmd,
            stderr=subprocess.STDOUT,
            shell=True,
            executable='/bin/bash')
    finally:
        print('Exited RUNNING_ONBUILD')
        LOCK_ONBUILD.release()

if __name__ == '__main__':
    PORT = 8002
    if 'DOCKERHUB_WH_PORT' in os.environ:
        PORT = int(os.environ['DOCKERHUB_WH_PORT'])
    SERVER = HTTPServer(('localhost', PORT), RequestHandler)
    print(f'Starting dockerhub hook listener at http://localhost:{PORT}')
    SERVER.serve_forever()
