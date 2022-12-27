from time import time
from datetime import datetime
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for
from flask import request
from flask import session
from flask import make_response
from markupsafe import escape
import sys
import os
import subprocess
from sfapi import Sfapi

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
import secrets
import string

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = ("https://accounts.google.com/.well-known/openid-configuration")
client = WebApplicationClient(GOOGLE_CLIENT_ID)

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
        print(f"get_google_ids: ERROR: Google ID list not found: {fnam}")
    return gids

app = Flask(__name__, static_url_path='/home/descprod/static')

class Data:
    dbg = True                 # Noisy if true.
    use_cookie_key = True      # If true session key is obtained from cookie.
    cookie_key_lifetime = 300  # Lifetime to set for cookie keys
    users = {}                 # Map of active users indexed by session key
    current = None             # Cache the current user
    session_count = 0
    msg = ''               # Error message shown once on home page.
    site = subprocess.getoutput('cat /home/descprod/data/etc/site.txt')
    google_ids = get_google_ids()
    lognam = None      # Job log file
    stanam = None      # Last line is status or processing
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
    def get(cls):
        """
        Return the data for the current session.
        If a user is logged in, then userkey, user_name etc. will be set.
        If not, userkey is None.
        """
        if Data.current is not None: return Data.current
        if Data.use_cookie_key:
            userkey = request.cookies.get('userkey')
            if userkey is None:
                if Data.dbg: print('Data.get: Cookie with user key not found.')
        else:
            if 'userkey' not in session:
                if Data.dbg: print('Data.get: Session does not have a key')
            userkey = session['userkey']
            session.modified = True    # Reset session timeout timer
        if userkey in cls.users:
            return cls.users[userkey]
        if userkey is not None:
            print(f"Data.get: ERROR: Unknown user key: {userkey}")
            print(f"Data.get: ERROR: Known keys: {cls.users.keys()}")
            userkey = None
        user_name = 'nologin'
        if userkey not in cls.users:
            if Data.dbg: print(f"Data.get: Creating session data for {user_name}")
            cls.users[userkey] = Data(userkey, user_name, {})
        return cls.users[userkey]
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
    def __init__(self, userkey, user_name='', user_info={}):
        """Add an active user."""
        self.userkey = userkey
        self.user_name = user_name
        self.user_info = user_info
        assert userkey not in Data.users
        Data.users[userkey] = self
        print(f"Data.init: Updated active user count is {len(Data.users)}")
        assert userkey in Data.users
    def make_response(self, rdat):
        """
        Make an HTML response from the provided response data.
        Typically called from home().
        if Data.use_cookie_key is true, then create a new userkey cookie with
        the value Data.cookie_key and lifetime Data.cookie_key_lifetime.
        """
        resp = make_response(rdat)
        if Data.use_cookie_key:
            if self.userkey is None:
                resp.set_cookie('userkey', '', expires=0)
            else:
                texp = datetime.timestamp(datetime.now()) + Data.cookie_key_lifetime
                resp.set_cookie('userkey', str(self.userkey), expires=texp)
        else:
            session.modified = True
        Data.current = None
        return resp

# Get the base url from a flask request.
def fixurl(url):
    if Data.force_https:
        url = url.replace('http:', 'https:', 1)
    return url

if __name__ == '__main__':
    app.run(ssl_context=('/home/descprod/cert.pem', 'key.pem'))
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(minutes=5)
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
    """
    Create and return the home page.
    Most http commands will redirect here.
    If the session doe not have an active user, generic data is displayed
    along with a button to log in.
    If the session is for an authenticated user, his or her info is displayed.
    if Data.msg has content, it is displayed near the top iof the page and then
    cleared so it will not appear when the page is refreshed.
    The lifetime of the session or cookie  user key is refreshed.
    """
    #return render_template('index.html')
    if Data.dbg: print('home: Constructing home page.')
    sep = '<br>\n'
    msg = '<h2>DESCprod</h2>'
    msg += sep
    udat = Data.get()
    if Data.dbg: print(f"home: User is {udat.user_name} [{udat.userkey}]")
    have_user = udat.userkey is not None
    if have_user:
        if Data.msg is not None and len(Data.msg):
            msg += f"<hr>\n{Data.msg}\n<hr>\n<br>"
            Data.msg = None
    msg += f"Site: {Data.site}"
    msg += sep
    if have_user:
        msg += f"User: {udat.user_name}"
        msg += f" [{udat.userkey}]"
        msg += sep
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
        if udat.user_info is not None and ready():
            msg += sep
            msg += sep
            msg += f'''\nParsltest job: <form action="/form_parsltest" method='POST'><input type="text" name="config"/><input type="submit" value="Submit"/></form>'''
            msg += sep
        msg += '<form action="/" method="get"><input type="submit" value="Refresh"></form>'
        msg += '<form action="/logout" method="get"><input type="submit" value="Log out"></form>'
        msg += '<form action="/help" method="get"><input type="submit" value="Help"></form>'
        msg += '<form action="/versions" method="get"><input type="submit" value="Versions"></form>'
        msg += '<form action="/session" method="get"><input type="submit" value="Show session"></form>'
        msg += '<form action="/pmstatus" method="get"><input type="submit" value="Perlmutter status"></form>'
        msg += '<form action="/bye" method="get"><input type="submit" value="Restart server"></form>'
    else:
        msg += sep
        msg += '<form action="/login" method="get"><input type="submit" value="Log in with google"></form>'
    return udat.make_response(msg)

@app.route("/login")
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri = fixurl(request.base_url) + "/callback"
    # For anything but local host, make sure redirect is https.
    if redirect_uri[0:5] == 'http:' and redirect_uri.find('localhost') < 0 and redirect_uri.find('127.0.0.1') < 0:
        redirect_uri = redirect_uri.replace('http:', 'https:')
    if Data.dbg: print(f"login: URI: {redirect_uri}")
    scope=["openid", "email", "profile"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=scope
    )
    if Data.dbg: print(f"login: Auth: {authorization_endpoint}")
    if Data.dbg: print(f"login: Request: {request_uri}")
    res = redirect(request_uri)
    if Data.dbg: print(f"login: Result: {res}")
    return res

@app.route("/logout")
def logout():
    udat = Data.get()
    if udat is None:
        print('logout: Logout requested without login. Might be expired.')
    else:
        del Data.users[userkey]
    session['userkey'] = None
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
    msg += '<br>       versions - Show perlmutter status'
    msg += '<br>      parsltest - Parses a request'
    return msg

@app.route("/bye")
def bye():
    print("bye: Shutting down.")
    os.kill(os.getpid(), 9)
    return ""

@app.route("/login/callback")
def callback():
    if Data.dbg: print('callback: Handling google callback')
    # Fetch tokens.
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    if request.is_secure:
        authresp = fixurl(request.url)
    else:
        authresp = None
    print(f"callback: **************** authresp: {authresp}")
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response = authresp,
        redirect_url = fixurl(request.base_url),
        code = code
    )
    if Data.dbg:
        print('callback: --------- BEGIN Token post')
        print(f"callback: token_url: {token_url}")
        print(f"callback: headers: {headers}")
        print(f"callback: token_url: {token_url}")
        print(f"callback: data: {body}")
        print(f"callback: auth: {GOOGLE_CLIENT_ID}, *****")
        print('callback: --------- END Token response')
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    resp = token_response.json()
    if Data.dbg:
        print('callback: --------- BEGIN Token response')
        for key in resp:
            print(f"callback: {key}: {resp[key]}")
        print('callback: --------- END Token response')
    # Parse tokens and fetch user profile.
    client.parse_request_body_response(json.dumps(resp))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    user_info = userinfo_response.json()
    user_id      = user_info["sub"]
    user_name    = user_info["name"]
    user_label = f"{user_name} ({user_id})"
    #print(f"callback: User info: {user_info")
    resp = redirect(url_for('home'))
    udata = None
    if userinfo_response.json().get("email_verified"):
        if user_id in Data.google_ids:
            print(f"callback: Authorizing  {user_label}")
            user_info    = userinfo_response.json()
            if Data.use_cookie_key:
                # The cookie is created in udat.make_response
                # We need a string key.
                userkey = ''.join(secrets.choice(string.ascii_letters+string.digits) for i in range(24))
            else:
                userkey = app.secret_key = os.urandom(16)
                session['userkey'] = userkey
                session['user_name'] = user_name
                user_index = Data.session_count
                session['index'] = user_index
                session.permanent = True   # This enables the session to expire
            Data.session_count += 1
        else:
            print(f"callback: Denying unauthorized user {user_label}")
            Data.msg = f"User not authorized: {user_id} {user_name}"
            Data.msg += f"\n<br>Send the above line to adminn@descprod.org request authorization."
    else:
        print(f"callback: Denying unverified user {user_label}")
        Data.msg = "User is not verified Google: {user_label}"
    Data.current = Data(userkey, user_name, user_info)
    return redirect(url_for('home'))

@app.route("/versions")
def versions():
    #return f"{os.getcwd()}<br>{__file__}"
    sep = '<br>\n'
    tbl = {}
    msg = subprocess.getoutput('/home/descprod/dev/desc-prod/ptenv/ptenv-versions')
    for line in msg.split('\n'):
        prod = line.split()[0]
        vers = line[len(prod):]
        tbl[prod.strip()] = vers.strip()
    tbl['desc-prod'] = subprocess.getoutput('cat /home/descprod/dev/desc-prod/version.txt')
    msg = '<table>\n'
    for prod in tbl:
        msg += f"<tr><td>{prod}</td><td>{tbl[prod]}</td></tr>\n"
    msg += '</table>\n'
    Data.msg = msg
    return redirect(url_for('home'))

@app.route("/pmstatus")
def pmstatus():
    sfapi = Sfapi()
    Data.msg = sfapi.get_status()
    return redirect(url_for('home'))
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
    print(f"parsltest: {args}")
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


@app.route('/session')
def show_session():
    print(session)
    msg = 'Session data:\n'
    for key in session.keys():
        msg += f"<br>{key}: {session[key]}\n"
    print(msg)
    Data.msg = msg
    return redirect(url_for('home'))

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

