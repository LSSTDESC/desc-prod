from time import time
from datetime import datetime
from flask import Flask, render_template, redirect, url_for
from flask import request
from markupsafe import escape
import sys
import os
import subprocess

import json
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user
)
from oauthlib.oauth2 import WebApplicationClient
import requests

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = ("https://accounts.google.com/.well-known/openid-configuration")
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

app = Flask(__name__)
if __name__ == '__main__':
    app.run(ssl_context=('/home/descprod/cert.pem', 'key.pem'))
app.secret_key = os.urandom(24)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def get_jobid():
    fnam  = '/home/descprod/data/etc/jobid.txt'
    jobid = int(subprocess.getoutput(f"descprod-next-jobid"))
    return jobid

class Data:
    msg = ''
    site = subprocess.getoutput('cat /home/descprod/data/etc/site.txt')
    lognam = None   # Job log file
    stanam = None   # Last line is status or processing
    cfgnam = 'config.txt'   # Name for config file describing ther job
    logfil = None
    sjobid = None
    fout = None
    sjob = None
    rundir = None
    com = None
    ret = None
    @classmethod
    def write_config(cls):
        myname = 'Data.write_config'
        if cls.rundir is None:
            print(f"{myname}: Cannot write config without rundir")
            return None
        msg = ""
        sep = "\n"
        msg += f"Time: {time()}"
        msg += sep
        msg += f"Command: {cls.com}"
        msg += sep
        msg += f"Site: {cls.site}"
        msg += sep
        msg += f"Rundir: {cls.rundir}"
        msg += sep
        cpat = f"{cls.rundir}/{cls.cfgnam}"
        cout = open(cpat, 'w')
        cout.write(msg)
        cout.close()
        return 0

@app.route("/")
def home():
    #return render_template('index.html')
    sep = '<br>\n'
    msg = '<h2>DESCprod</h2>'
    msg += f"Site: {Data.site}"
    msg += sep
    msg += f"{status()}"
    if Data.stanam is not None:
        sjstat = 'Not found'
        try:
            jsin = open(Data.stanam, 'r')
            sjtext = jsin.readlines()
            if len(sjtext): sjstat = sjtext[-1]
        except FileNotFoundError:
            sjstat = f"File not found: {Data.stanam}"
        msg += sep
        msg += f"Status: {sjstat}"
    if Data.sjobid is not None:
      msg += sep
      msg += f"Config: {Data.sjob}"
      msg += sep
      msg += f"Command: {Data.com}"
      msg += sep
      msg += f"Run dir: {Data.rundir}"
    msg += sep
    msg += sep
    if ready():
        msg += f'''\nParsltest job: <form action="/form_parsltest" method='POST'><input type="text" name="config"/><input type="submit" value="Submit"/></form>'''
        msg += sep
    msg += '<form action="/" method="get"><input type="submit" value="Refresh"></form>'
    if current_user.is_authenticated:
        pass
    else:
        msg += '<form action="/login" method="get"><input type="submit" value="Log in with google"></form>'
    msg += '<form action="/help" method="get"><input type="submit" value="Help"></form>'
    msg += '<form action="/versions" method="get"><input type="submit" value="Versions"></form>'
    msg += '<form action="/bye" method="get"><input type="submit" value="Restart server"></form>'
    return msg

@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri=request.base_url + "/callback",
    print(f"URI: {redirect_uri}")
    scope=["openid", "email", "profile"]
    scope=["openid"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=scope
    )
    print(f"Request: {request_uri}")
    res = redirect(request_uri)
    print(f"Result: {res}")
    return res

@app.route("/help")
def help():
    msg = '<H1>Hello help</H1>'
    msg +=      '          help - This message.'
    msg += '<br>            bye - Restarts the server.'
    msg += '<br>     hello?John - Says hello to John'
    msg += '<br> hello?John&Doe - Says hello to John Doe'
    msg += '<br>        request - Parses a request'
    msg += '<br>       versions - Show software versions'
    msg += '<br>      parsltest - Parses a request'
    return msg

@app.route("/bye")
def bye():
    print("Shutting down.")
    os.kill(os.getpid(), 9)
    return ""

@app.route("/login/callback")
def callback():
    print('called back')
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_responase=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    client.parse_request_body_response(json.dumps(token_response.json()))
    return "Done"

@app.route("/versions")
def versions():
    sep = '<br>\n'
    msg = subprocess.getoutput('/home/descprod/dev/desc-prod/ptenv/ptenv-versions').replace('\n', sep)
    msg += sep
    msg += 'desc-prod ' + subprocess.getoutput('cat /home/descprod/dev/desc-prod/version.txt')
    msg += sep
    msg += sep
    msg += '<form action="/" method="get"><input type="submit" value="Home"></form>'
    return msg

@app.route("/hello")
def hello():
    name = ''
    if len(request.args):
        for snam in request.args:
            name += ' ' + snam
    else:
        name = ' NOONE'
    if len(Data.msg) == 0:
        Data.msg = "<h1>Hellos from desc-prod</h1>"
    Data.msg += f"hello{name}</br>"
    return Data.msg

@app.route('/parsltest')
def run_parsltest():
    myname = 'run_parsltest'
    if 'config' not in request.args.keys():
          return "Invalid job description"
    args = request.args.get('config')
    print(args)
    return do_parsltest(args)

@app.route('/form_parsltest/', methods=['POST', 'GET'])
def run_form_parsltest():
    if request.method == 'GET':
        return 'Got GET instead of POST!!'
    print(request.form['config'])
    return do_parsltest(request.form['config'])

def do_parsltest(args):
    myname = 'do_parsltest'
    fout = Data.fout
    if Data.sjob is not None and Data.ret is None:
        return f"Job is already running: {Data.sjob}"
    if Data.ret is not None:
        rcode = Data.ret.poll()
        if rcode is None:
            msg = f"Earlier job {Data.sjob} is still running."
            return msg
        Data.ret = None
    Data.sjobid = str(get_jobid())
    while len(Data.sjobid) < 6: Data.sjobid = '0' + Data.sjobid
    Data.rundir = f"/home/descprod/data/rundirs/job{Data.sjobid}"
    os.mkdir(Data.rundir)
    Data.sjob = args
    Data.com = ['desc-wfmon-parsltest', args]
    if fout is not None:
        fout.close() 
    rout = open(f"{Data.rundir}/README.txt", 'w')
    rout.write(f"{Data.sjob}\n")
    rout.close()
    Data.lognam = f"{Data.rundir}/job{Data.sjobid}.log"
    Data.stanam = f"{Data.rundir}/current-status.txt"
    Data.write_config()
    print(f"{myname}: Opening {Data.lognam}")
    Data.logfil = open(Data.lognam, 'w')
    Data.ret = subprocess.Popen(Data.com, cwd=Data.rundir, stdout=Data.logfil, stderr=Data.logfil)
    sep = '<br>\n'
    msg = f"Started {Data.com[0]} {Data.com[1]} in {Data.rundir}"
    msg += sep
    msg += '<form action="/" method="get"><input type="submit" value="Home"></form>'
    return msg

def ready():
    if Data.sjob is None: return True
    rcode = Data.ret.poll()
    if rcode is None: return False
    # Post job actions go here.
    return True

@app.route('/status')
def status():
    if Data.sjob is None:
        msg = "No job is started."
    else:
        rcode = Data.ret.poll()
        if ready():
            msg = f"Job {Data.sjobid} returned {Data.ret.poll()}."
        else:
            msg = f"Job {Data.sjobid} is running."
    return msg

@app.route("/request")
@app.route("/<path:path>")
def req(path):
    msg = ''
    msg += f"      url: {request.url}<br><br>"
    msg += f"root path: {request.root_path}<br><br>"
    msg += f"     path: {request.path}<br><br>"
    msg += f"   method: {request.method}<br><br>"
    msg += f"     endp: {request.endpoint}<br><br>"
    msg += f"     args: {request.args}<br><br>"
    msg += f"     form: {request.form}<br><br>"
    msg += f"     data: {request.data.decode('UTF-8')}<br><br>"
    msg += f"     json:"
    if request.is_json:
        msg += f"{request.get_json()}"
    msg += f"<br><br>"
    msg += f" get data: {request.get_data().decode('UTF-8')}<br><br>"
    return msg

