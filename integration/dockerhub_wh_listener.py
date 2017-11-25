"""Python server that processes docker hub webhook call when a build
of hmalphettes/s3-storage-analyser is completed"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from pprint import pprint
import subprocess
import threading
import os
import json

# Run a single onbuild or analysis at a time
LOCK_ONBUILD = threading.Lock()
LOCK_ANALYSIS = threading.Lock()

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

        query_components = {
            'token': None,
            'unit': None,
            'prefix': None,
            'conc': None,
            'fmt': None,
            'pretty': None
        }
        query = urlparse(self.path).query
        if query:
            query_components.update(dict(qc.split("=") for qc in query.split('&')))

        if query_components['token'] != token:
            # redirect to github if the token is missing
            self.send_response(302)
            self.send_header('Location', 'https://github.com/hmalphettes/s3-storage-analyser')
            self.end_headers()
            return

        unit = query_components['unit']
        prefix = query_components['prefix']
        conc = query_components['conc']
        fmt = query_components['fmt']
        echo = 'echo' in query_components
        if fmt is None:
            accept = self.headers['Accept'] if 'Accept' in self.headers else ''
            print(f'accept: {accept}')
            if query_components.get('pretty'):
                fmt = 'json_pretty'
            elif 'json' in accept:
                fmt = 'json'
            elif 'csv' in accept:
                fmt = 'csv'
            elif 'tab-separated-values' in accept:
                fmt = 'tsv'
            elif 'text/plain' in accept:
                fmt = 'plain'
            elif 'html' in accept:
                fmt = 'html'
            else:
                fmt = 'json'

        # sanitize before we call docker
        for param in [unit, prefix, conc, fmt]:
            if param is None:
                continue
            for char in [ ';', '|', '&', ' ', '\t', '"' ]:
                if char in param:
                    self.send_response(401)
                    self.end_headers()
                    return

        try:
            out = _run_analysis(unit=unit, prefix=prefix, conc=conc, fmt=fmt, echo=echo)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(out)
        except subprocess.CalledProcessError as err:
            msg = f'{err.__str__()} {err.output}'
            print(f'Analysis - Subprocess Error {msg}')
            self.send_response(500)
            self.end_headers()
            self.wfile.write(msg.encode())
        except Exception as err:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(err.__str__().encode())
        return


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
    try:
        if not LOCK_ONBUILD.acquire(False):
            print('There is already an onbuild running')
            raise ValueError('There is already an onbuild running')
        script_dir = os.path.dirname(os.path.realpath(__file__))
        full_cmd = f'bash {script_dir}/onbuild.sh {repo_name} {tag}'
        print(f'Entered RUNNING_ONBUILD {full_cmd}')
        return subprocess.check_output(
            full_cmd.split,
            stderr=subprocess.STDOUT,
            shell=True,
            executable='/bin/bash')
    finally:
        print('Exited RUNNING_ONBUILD')
        LOCK_ONBUILD.release()

def _run_analysis(unit=None, prefix=None, conc='6', fmt=None, echo=False):
    # full_cmd = 'docker images'
    full_cmd = f'docker run --rm --net host hmalphettes/s3-storage-analyser'
    if fmt is not None:
        full_cmd += f' --fmt "{fmt}"'
    if unit is not None:
        full_cmd += f' --unit "{unit}"'
    if prefix is not None:
        full_cmd += f' --prefix "{prefix}"'
    if conc is not None:
        full_cmd += f' --conc "{conc}"'
    print(full_cmd)
    if echo:
        return full_cmd.encode()
    try:
        print(f'Entered RUNNING_ANALYSIS {full_cmd}')
        if not LOCK_ANALYSIS.acquire(False):
            raise ValueError('There is already an analysis running')
        return subprocess.check_output(
            full_cmd,
            stderr=subprocess.STDOUT,
            shell=True,
            executable='/bin/bash')
    finally:
        print('Exited RUNNING_ANALYSIS')
        LOCK_ANALYSIS.release()

if __name__ == '__main__':
    SERVER = HTTPServer(('localhost', 8000), RequestHandler)
    print('Starting server at http://localhost:8000')
    SERVER.serve_forever()
