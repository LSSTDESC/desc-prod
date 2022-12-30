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

# Return map of [username, googlename] indexed by authorized google IDs.
# File lines are:
#  username google-id google-name
# The last may include single spaces
def get_google_ids():
    gids = {}
    fnam = '/home/descprod/data/etc/google_ids.txt'
    try:
        fids = open(fnam)
        for line in fids.readlines():
            words = line.split()
            if len(words):
                unam = words[0]
                gid = words[1]
                gnam = ' '.join(words[2:])
                gids[gid] = [unam, gnam]
        fids.close()
    except FileNotFoundError:
        print(f"get_google_ids: ERROR: Google ID list not found: {fnam}")
    return gids

app = Flask(__name__, static_url_path='/home/descprod/static')

from descprod import UserData
from descprod import JobData
from descprod import JobTable

class SessionData:
    """
    The SessionData class holds global data for the service and its sessions.
    SessionData objects describe sessions.
    """
    dbg = False                 # Log is noisy if true.
    use_cookie_key = True       # If true session key is obtained from cookie.
    cookie_key_lifetime = 3600  # Lifetime [sec] to set for cookie keys.
    sessions = {}               # Map of active sessions indexed by session key
    current = None              # Cache the current session
    site = subprocess.getoutput('cat /home/descprod/data/etc/site.txt')
    google_ids = get_google_ids()  # [descname, fullname] indexed by google ID
    lognam = None      # Job log file
    stanam = None      # Last line is status or processing
    cfgnam = 'config.txt'   # Name for config file describing ther job
    logfil = None
    fout = None
    sjob = None
    rundir = None
    com = None
    ret = None
    force_https = False
    @classmethod
    def nologin_session(cls):
        """Fetch the data for the no-login session."""
        if None not in SessionData.sessions:
            SessionData.sessions[None] = SessionData(None, 'nologin', {})
        return SessionData.sessions[None]
    @classmethod
    def get(cls):
        """
        Return the data for the current session.
        If a user is logged in, then sesskey, descname, fullname, login_info etc. will be set.
        If not, sesskey is None and name is 'nologin'.
        """
        if SessionData.current is not None: return SessionData.current
        if SessionData.use_cookie_key:
            sesskey = request.cookies.get('sesskey')
            if sesskey is None:
                if SessionData.dbg: print('SessionData.get: Cookie with user key not found.')
        else:
            if 'sesskey' in session:
                sesskey = session['sesskey']
            else:
                if SessionData.dbg: print('SessionData.get: Session does not have a key')
                sesskey = None
        if sesskey in cls.sessions:
            SessionData.current = cls.sessions[sesskey]
        else:
            if sesskey is not None:
                print(f"SessionData.get: ERROR: Unexpected session key: {sesskey}")
                print(f"SessionData.get: ERROR: Known keys: {cls.sessions.keys()}")
            SessionData.current = SessionData.nologin_session()
        return SessionData.current
    def __init__(self, sesskey, descname, fullname=None, login_info={}):
        """Add an active user."""
        self.sesskey = sesskey
        self.descname = descname
        self.fullname = fullname
        self.login_info = login_info
        self.session_id = 0 if sesskey is None else get_sessionid()
        self.msg = ''               # Error message shown once on home page.
        self._user = None
        assert sesskey not in SessionData.sessions
        SessionData.sessions[sesskey] = self
        print(f"SessionData.init: Updated active user count is {len(SessionData.sessions)}")
        assert sesskey in SessionData.sessions
    def user(self):
        if self._user is None:
            self._user = UserData.get(self.descname)
        return self._user
    def make_response(self, rdat):
        """
        Make an HTML response from the provided response data.
        Typically called from home().
        if SessionData.use_cookie_key is true, then create a new sesskey cookie with
        the value SessionData.cookie_key and lifetime SessionData.cookie_key_lifetime.
        """
        resp = make_response(rdat)
        if SessionData.use_cookie_key:
            if self.sesskey is None:
                resp.set_cookie('sesskey', '', expires=0)
            else:
                texp = datetime.timestamp(datetime.now()) + SessionData.cookie_key_lifetime
                resp.set_cookie('sesskey', str(self.sesskey), expires=texp)
        else:
            session.modified = True
        SessionData.current = None
        return resp

# Get the base url from a flask request.
def fixurl(url):
    if SessionData.force_https:
        url = url.replace('http:', 'https:', 1)
    return url

def html_head():
    msg = '<!DOCTYPE html>\n'
    msg += '<html lang="en">\n'
    msg += '<head>\n'
    msg += '  <link rel="stylesheet" href="/home/descprod/static/main.css" />\n'
    #msg += '  <script>alert("loaded page")</script>'
    msg += '</head>\n'
    return msg

def table_wrap(inmsg):
    msg = ''
    msg += '<div class="p-Widget jp-RenderedHTMLCommon jp-RenderedHTML jp-mod-trusted jp-OutputArea-output" data-mime-type="text/html">\n'
    #msg += '<style scoped="">\n'
    #msg += '  .dataframe tbody tr th:only-of-type { vertical-align: middle; }\n'
    #msg += '  .dataframe tbody tr th { vertical-align: top; }\n'
    #msg += '  .dataframe thead th { text-align: right; }\n'
    #msg += '</style>'
    msg += inmsg
    msg += '\n</div>\n'
    return msg

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
            SessionData.dbg = True
        elif opt == 'force-https':
            SessionData.force_https = True
        else:
            print(f"Ignoring invalid option {opt}")

def get_jobid():
    fnam  = '/home/descprod/data/etc/jobid.txt'
    jobid = int(subprocess.getoutput(f"descprod-next-jobid"))
    return jobid

def get_sessionid():
    lines = subprocess.getoutput(f"descprod-next-sessionid").splitlines()
    sesid = int(lines[-1])
    for line in lines[0:-1]:
        print(f"get_sessionid: {line}")
    if SessionData.dbg: print(f"get-sessionid: Session ID is {sesid}")
    return sesid

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
    if sdat.msg has content, it is displayed near the top iof the page and then
    cleared so it will not appear when the page is refreshed.
    It can be either a string or a list of strings.
    The lifetime of the session or cookie  user key is refreshed.
    """
    #return render_template('index.html')
    if SessionData.dbg: print('home: Constructing home page.')
    sep = '<br>\n'
    msg = html_head()
    msg += '<h2>DESCprod</h2>\n'
    sdat = SessionData.get()
    udat = sdat.user()
    if SessionData.dbg: print(f"home: User is {sdat.user_name} [{sdat.sesskey}]")
    have_user = sdat.sesskey is not None
    if have_user:
        if sdat.msg is not None and len(sdat.msg):
            msg += f"<hr>\n"
            if not isinstance(sdat.msg, list): lines = [sdat.msg]
            else: lines = sdat.msg
            for line in lines:
                msg += f"{line}{sep}"
            msg += f"<hr>{sep}"
            sdat.msg = None
    msg += f"Site: {SessionData.site}"
    msg += sep
    if have_user:
        msg += f"User: {sdat.descname}"
        if sdat.fullname is not None: msg+= f" ({sdat.fullname})"
        #msg += f" [{sdat.sesskey}]"
        msg += sep
        #msg += f"Login info: {sdat.login_info}"
        #msg += sep
        msg += f"Session: {sdat.session_id}"
        #msg += f" [{sdat.sesskey}]"
        msg += sep
        msg += sep
        jtab = JobTable(udat.descname)
        njob = len(jtab.jobs)
        msg += f"User {udat.descname} has {njob} job"
        if njob != 1: msg += 's'
        if njob:
            msg += ':'
            msg += sep
            msg += table_wrap(jtab.to_html())
        msg += sep
        #msg += f"{status()}"
        #if SessionData.stanam is not None:
        #    sjstat = 'Not found'
        #    try:
        #        jsin = open(SessionData.stanam, 'r')
        #        sjtext = jsin.readlines()
        #        if len(sjtext): sjstat = sjtext[-1]
        #    except FileNotFoundError:
        #        sjstat = f"File not found: {SessionData.stanam}"
        #    msg += sep
        #    msg += f"Status: {sjstat}"
        #if SessionData.sjobid is not None:
        #    msg += sep
        #    msg += f"Config: {SessionData.sjob}"
        #    msg += sep
        #    msg += f"Command: {SessionData.com}"
        #    msg += sep
        #    msg += f"Run dir: {SessionData.rundir}"
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
    return sdat.make_response(msg)

@app.route("/login")
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri = fixurl(request.base_url) + "/callback"
    # For anything but local host, make sure redirect is https.
    if redirect_uri[0:5] == 'http:' and redirect_uri.find('localhost') < 0 and redirect_uri.find('127.0.0.1') < 0:
        redirect_uri = redirect_uri.replace('http:', 'https:')
    if SessionData.dbg: print(f"login: URI: {redirect_uri}")
    scope=["openid", "email", "profile"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=scope
    )
    if SessionData.dbg: print(f"login: Auth: {authorization_endpoint}")
    if SessionData.dbg: print(f"login: Request: {request_uri}")
    res = redirect(request_uri)
    if SessionData.dbg: print(f"login: Result: {res}")
    return res

@app.route("/logout")
def logout():
    sdat = SessionData.get()
    if sdat is None:
        print('logout: Logout requested without login. Might be expired.')
    else:
        del SessionData.sessions[sdat.sesskey]
    session['sesskey'] = None
    SessionData.current = SessionData.nologin_session()
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
    if SessionData.dbg: print('callback: Handling google callback')
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
    if SessionData.dbg:
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
    if SessionData.dbg:
        print('callback: --------- BEGIN Token response')
        for key in resp:
            print(f"callback: {key}: {resp[key]}")
        print('callback: --------- END Token response')
    # Parse tokens and fetch user profile.
    client.parse_request_body_response(json.dumps(resp))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    login_info = userinfo_response.json()
    google_id      = login_info["sub"]
    fullname    = login_info["name"]
    user_label = f"{fullname} ({google_id})"
    #print(f"callback: User info: {login_info")
    resp = redirect(url_for('home'))
    sdat = SessionData.nologin_session()
    if userinfo_response.json().get("email_verified"):
        if google_id in SessionData.google_ids:
            print(f"callback: Authorizing  {user_label}")
            login_info    = userinfo_response.json()
            if SessionData.use_cookie_key:
                # The cookie is created in sdat.make_response
                # We need a string key.
                sesskey = ''.join(secrets.choice(string.ascii_letters+string.digits) for i in range(24))
            else:
                sesskey = app.secret_key = os.urandom(16)
                session['sesskey'] = sesskey
                session['fullname'] = fullname
                session.permanent = True   # This enables the session to expire
            descname = SessionData.google_ids[google_id][0]
        else:
            print(f"callback: Denying unauthorized user {user_label}")
            sdat.msg = f"User not authorized: {google_id} {fullname}"
            sdat.msg += f"\n<br>Send the above line to adminn@descprod.org request authorization."
    else:
        print(f"callback: Denying unverified user {user_label}")
        sdat.msg = "User is not verified Google: {user_label}"
    if sesskey is not None:
        sdat = SessionData(sesskey, descname, fullname, login_info)
        if not SessionData.use_cookie_key:
            session['session_id'] = sdat.session_id
        SessionData.current = sdat
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
    SessionData.get().msg = msg
    return redirect(url_for('home'))

@app.route("/pmstatus")
def pmstatus():
    sfapi = Sfapi()
    SessionData.get().msg = sfapi.get_status()
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
    sdat = SessionData.get()
    if len(sdat.msg) == 0:
        sdat.msg = "<h1>Hellos from desc-prod</h1>"
    sdat.msg += f"hello{name}</br>"
    return redirect(url_for('home'))

@app.route('/parsltest')
def run_parsltest():
    myname = 'run_parsltest'
    if 'config' not in request.args.keys():
          return "Invalid job description"
    cfg = request.args.get('config')
    print(f"parsltest: {cfg}")
    return do_parsltest(cfg)

@app.route('/form_parsltest/', methods=['POST', 'GET'])
def run_form_parsltest():
    if request.method == 'GET':
        return 'Got GET instead of POST!!'
    print(request.form['config'])
    return do_parsltest(request.form['config'])

def do_parsltest(cfg):
    myname = 'do_parsltest'
    jobtype = 'parsltest'
    sdat = SessionData.get()
    udat = sdat.user()
    if udat.descname == 'nologin':
        sdat.msg = 'Log in to run parsltest'
        return redirect(url_for('home'))
    jobid = get_jobid()
    jdat = JobData(jobid, udat.descname, True)
    if len(jdat.errmsgs):
        sdat.msg = jdat.errmsgs
        return redirect(url_for('home'))
    if jdat.configure(jobtype, cfg):
        sdat.msg = jdat.errmsgs
        return redirect(url_for('home'))
    if jdat.run():
        sdat.msg = jdat.errmsgs
        return redirect(url_for('home'))
    sdat.msg = f"Started {jobtype} {cfg} in {jdat.rundir}"
    return redirect(url_for('home'))

def ready():
    if SessionData.sjob is None: return True
    rcode = SessionData.ret.poll()
    if rcode is None: return False
    # Post job actions go here.
    return True

@app.route('/status')
def status():
    if SessionData.sjob is None:
        msg = "No job is started."
    else:
        rcode = SessionData.ret.poll()
        if ready():
            msg = f"Job {SessionData.sjobid} returned {SessionData.ret.poll()}."
        else:
            msg = f"Job {SessionData.sjobid} is running."
    return msg


@app.route('/session')
def show_session():
    print(session)
    msg = 'Session data:\n'
    for key in session.keys():
        msg += f"<br>{key}: {session[key]}\n"
    print(msg)
    SessionData.get().msg = msg
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

