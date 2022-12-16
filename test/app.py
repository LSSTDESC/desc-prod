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

# Restore https behind a proxy.
def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

# Return map of authorized user IDs and names.
def get_google_ids():
    gids = {}
    fnam = '/home/descprod/data/etc/google_ids.txt'
    try:
        fids = open(fnam)
        for line in fids.readlines():
            words = line.split()
            if len(words):
                gid = words[0]
                nam = line.replace(gid, '').strip()
                gids[gid] = nam
        fids.close()
    except FileNotFoundError:
        print(f"ERROR: Google ID list not found: {fnam}")
    return gids

app = Flask(__name__)

class Data:
    dbg = False      # Noisy if true.
    msg = ''         # Error message show once on  home page.
    site = subprocess.getoutput('cat /home/descprod/data/etc/site.txt')
    google_ids = get_google_ids()
    user_info = None
    user_name = None
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
    force_https = False
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

# Get the base url from a flask request.
def fixurl(url):
    if Data.force_https:
        url = url.replace('http:', 'https:', 1)
    return url

if __name__ == '__main__':
    app.run(ssl_context=('/home/descprod/cert.pem', 'key.pem'))
app.secret_key = os.urandom(24)
login_manager = LoginManager()
login_manager.init_app(app)
if 'SERVER_OPTS' in os.environ:
    opts=os.environ['SERVER_OPTS'].split()
    for opt in opts:
        print(f"Processing server option {opt}")
        if opt == 'debug':
            Data.dbg = True
        elif opt == 'force-https':
            Data.force_https = True
        else:
            print(f"Ignoring invalid option {opt}")

def get_jobid():
    fnam  = '/home/descprod/data/etc/jobid.txt'
    jobid = int(subprocess.getoutput(f"descprod-next-jobid"))
    return jobid

@app.route("/")
def top():
    return redirect(url_for('home'))

@app.route("/home")
def home():
    #return render_template('index.html')
    sep = '<br>\n'
    msg = '<h2>DESCprod</h2>'
    if Data.msg is not None:
        msg += f"<h4>{Data.msg}</h4>"
        Data.msg = None
    msg += f"Site: {Data.site}"
    msg += sep
    msg += f"User: {Data.user_name}"
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
    if Data.user_info is not None and ready():
        msg += f'''\nParsltest job: <form action="/form_parsltest" method='POST'><input type="text" name="config"/><input type="submit" value="Submit"/></form>'''
        msg += sep
    msg += '<form action="/" method="get"><input type="submit" value="Refresh"></form>'
    if Data.user_info is None:
        msg += '<form action="/login" method="get"><input type="submit" value="Log in with google"></form>'
    else:
        msg += '<form action="/logout" method="get"><input type="submit" value="Log out"></form>'
    msg += '<form action="/help" method="get"><input type="submit" value="Help"></form>'
    msg += '<form action="/versions" method="get"><input type="submit" value="Versions"></form>'
    msg += '<form action="/bye" method="get"><input type="submit" value="Restart server"></form>'
    return msg

@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri = fixurl(request.base_url) + "/callback"
    # For anything but local host, make sure redirect is https.
    if redirect_uri[0:5] == 'http:' and redirect_uri.find('localhost') < 0 and redirect_uri.find('127.0.0.1') < 0:
        redirect_uri = redirect_uri.replace('http:', 'https:')
    if Data.dbg: print(f"URI: {redirect_uri}")
    scope=["openid", "email", "profile"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=scope
    )
    if Data.dbg: print(f"Auth: {authorization_endpoint}")
    if Data.dbg: print(f"Request: {request_uri}")
    res = redirect(request_uri)
    if Data.dbg: print(f"Result: {res}")
    return res

@app.route("/logout")
def logout():
    Data.user_info = None
    Data.user_name = None
    return redirect(url_for('home'))

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
    if Data.dbg: print('Handling google callback')
    Data.user_info = None
    Data.user_name = None
    # Fetch tokens.
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    if request.is_secure:
        authresp = fixurl(request.url)
    else:
        authresp = None
    print(f"**************** authresp: {authresp}")
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response = authresp,
        redirect_url = fixurl(request.base_url),
        code = code
    )
    if Data.dbg:
        print('--------- BEGIN Token post')
        print(f"token_url: {token_url}")
        print(f"headers: {headers}")
        print(f"token_url: {token_url}")
        print(f"data: {body}")
        print(f"auth: {GOOGLE_CLIENT_ID}, *****")
        print('--------- END Token response')
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    resp = token_response.json()
    if Data.dbg:
        print('--------- BEGIN Token response')
        for key in resp:
            print(f"{key}: {resp[key]}")
        print('--------- END Token response')
    # Parse tokens and fetch user profile.
    client.parse_request_body_response(json.dumps(resp))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    user_info = userinfo_response.json()
    user_id      = user_info["sub"]
    user_name    = user_info["name"]
    user_label = f"{user_name} ({user_id})"
    #print(f"User info: {user_info")
    if userinfo_response.json().get("email_verified"):
        if user_id in Data.google_ids:
            Data.user_info    = userinfo_response.json()
            Data.user_name    = user_name
            print(f"Authorizing  {user_label}")
        else:
            print(f"Denying unauthorized user {user_label}")
            Data.msg = f"User not authorized: {user_id} {user_name}"
    else:
        print(f"Denying unverified user {user_label}")
        Data.msg = "User is not verified Google: {user_label}"
    return redirect(url_for('home'))

@app.route("/versions")
def versions():
    sep = '<br>\n'
    tbl = {}
    msg = subprocess.getoutput('/home/descprod/dev/desc-prod/ptenv/ptenv-versions').replace('\n', sep)
    for line in msg.split('\n'):
        words = line.split()
        tbl[words[0]] = words[1:]
    return tbl
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

