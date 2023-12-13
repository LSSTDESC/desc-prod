import time
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
from oauthlib.oauth2 import WebApplicationClient
import requests
import secrets
import string

def fprint(txt):
    print(txt, flush=True)

def make_session_key():
    return ''.join(secrets.choice(string.ascii_letters+string.digits) for i in range(24))

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = ("https://accounts.google.com/.well-known/openid-configuration")
if 0:
    print(f"      GOOGLE_CLIENT_ID: {GOOGLE_CLIENT_ID}")
    print(f"  GOOGLE_CLIENT_SECRET: {GOOGLE_CLIENT_SECRET}")
    fprint(f"  GOOGLE_DISCOVERY_URL: {GOOGLE_DISCOVERY_URL}")
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Return map of [username, googlename] indexed by authorized google IDs.
# File lines are:
#  username google-id google-name
# The last may include single spaces
def get_google_ids():
    gids = {}
    fnam = '/home/descprod/local/etc/google_ids.txt'
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
        fprint(f"get_google_ids: ERROR: Google ID list not found: {fnam}")
    return gids

app = Flask(__name__, static_url_path='/home/descprod/static')

from descprod import sdate
from descprod import UserData
from descprod import JobData
from descprod import JobTable

# Move this to session.
class Refresh:
    def __init__(self):
        self.focus = True
        self.periods = [60, 3600, 0, 5]
        self.period_labels = ["1 minute", "1 hour", "Off", "5 sec"]
        self.iperiod = 0
    def focus_button_label(self):
        if self.focus: return "Disable focus refresh"
        return "Enable focus refresh"
    def change_focus(self):
        self.focus = not self.focus
        sfoc = 'True' if self.focus else 'False'
        fprint(f"Refresh on focus set to {sfoc} for sdat.user()")
    def period(self):
        return self.periods[self.iperiod]
    def period_label(self):
        return self.period_labels[self.iperiod]
    def increment_period(self):
        self.iperiod = (self.iperiod + 1) % len(self.periods)
        fprint(f"Set refresh period to index {self.iperiod}: {self.period_label()} [{self.period()} sec]")

class SessionData:
    """
    The SessionData class holds global data for the service and its sessions.
    SessionData objects describe sessions.
    """
    dbg = False                 # Log is noisy if true. Set with server option debug.
    use_cookie_key = True       # If true session key is obtained from cookie.
    cookie_key_lifetime = 3600  # Lifetime [sec] to set for cookie keys.
    sessions = {}               # Map of active sessions indexed by session key
    old_sessions = {}           # Map of old and now invalid sessions.
    arg_session_dict = {}       # Map of argument session key to actual (cookie) sesskey
    site = subprocess.getoutput('cat /home/descprod/local/etc/site.txt')
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
    secret = None
    @classmethod
    def nologin_session(cls):
        """Fetch the data for the no-login session."""
        if None not in SessionData.sessions:
            SessionData.sessions[None] = SessionData(None, 'nologin', {})
        return SessionData.sessions[None]
    @classmethod
    def get(cls):
        """
        Return the data for the current session using the sesskey cookie.
        If a user is logged in, then sesskey, descname, fullname, login_info etc. will be set.
        If not, sesskey is None and name is 'nologin'.
        """
        arg_sesskey = request.args.get('sesskey')
        sesskey = request.cookies.get('sesskey') if inkey is None else inkey
        if arg_sesskey is not None:
            if sskey is not None:
                fprint("Ignoring request to change user")
            elif arg_sesskey in SessionData.arg_session_dict:
                sesskey = arg_sesskey
                fprint("SessionData.get: Using argument session ID.")
            else:
                fprint("SessionData.get: Ignoring unknown argument session ID.")
        if sesskey is None:
            if SessionData.dbg: fprint('SessionData.get: Cookie with user key is not present.')
        elif sesskey in cls.sessions:
            if SessionData.dbg: fprint(f"SessionData.get: Session ID is {cls.sessions[sesskey].session_id} (key {sesskey}).")
            return cls.sessions[sesskey]
        elif sesskey in cls.old_sessions:
            if SessionData.dbg: fprint(f"SessionData.get: Session ID {cls.old_sessions[sesskey]} (key {sesskey}) was terminated.")
        else:
            fprint(f"SessionData.get: ERROR: Unexpected session key: {sesskey}")
            fprint(f"SessionData.get: ERROR: Known keys: {list(cls.sessions.keys())}")
        return SessionData.nologin_session()
    def __init__(self, sesskey, descname, fullname=None, login_info={}):
        """Add an active user."""
        self.sesskey = sesskey
        self.descname = descname
        self.fullname = fullname
        self.login_info = login_info
        self.session_id = 0 if sesskey is None else get_sessionid()
        self.msg = []               # Error message shown once on home page.
        self._user = None
        self.logged_out = False
        self.user()
        self.refresh = Refresh()
        assert sesskey not in SessionData.sessions
        SessionData.sessions[sesskey] = self
        fprint(f"SessionData.init: Updated active user count is {len(SessionData.sessions)}")
        assert sesskey in SessionData.sessions
    def user(self):
        if self._user is None:
            self._user = UserData.get(self.descname)
            rstat, self.msg = self._user.check_dirs()
        return self._user
    def logout():
        sdat.logged_out = True
        SessionData.old_sessions[sdat.sesskey] = sdat
        del(SessionData.sessions[sdat.sesskey])
        return cls.nologin_session()
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
    #msg += f"""  <link rel="stylesheet" href="{{ url_for('static', filename='main.css') }}">"""
    msg += '<style>\n'
    msg += '.dataframe table, th, td {font-size:12pt; border: none; padding-left: 20px; text-align:right;}\n'
    msg += '.dropbtn {\n'
    #msg += '  background-color: #04AA6D;\n'
    #msg += '  color: white;\n'
    msg += '  padding: 0px;\n'
    msg += '  font-family: inherit;\n'
    msg += '  font-size: 90%;\n'
    #msg += '  border: none;\n'
    msg += '  cursor: pointer;\n'
    msg += '}\n'
    msg += '.dropdown {\n'
    msg += '  position: relative;\n'
    msg += '  float: left;\n'
    msg += '  display: inline-block;\n'
    msg += '}\n'
    msg += '.dropdown-content {\n'
    msg += '  display: none;\n'
    msg += '  position: absolute;\n'
    msg += '  background-color: #f9f9f9;\n'
    #msg += '  box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);\n'
    msg += '  white-space: nowrap;\n'
    msg += '  text-align: left;\n'
    msg += '  line-height: 1.4;\n'
    msg += '  padding: 5px 5px;\n'
    msg += '  font-size: 18px;\n'
    msg += '  z-index: 1;\n'
    msg += '}\n'
    msg += '.dropdown:hover .dropdown-content {\n'
    msg += '  display: block;\n'
    msg += '}\n'
    msg += '</style>\n'
    #msg += '  <script>alert("loaded page")</script>'
    msg += '</head>\n'
    return msg

def table_wrap(inmsg):
    msg = ''
    #msg += '<div class="p-Widget jp-RenderedHTMLCommon jp-RenderedHTML jp-mod-trusted jp-OutputArea-output" data-mime-type="text/html">\n'
    #msg += '<style scoped="">\n'
    #msg += '  .dataframe tbody tr th:only-of-type { vertical-align: middle; }\n'
    #msg += '  .dataframe tbody tr th { vertical-align: top; }\n'
    #msg += '  .dataframe thead th { text-align: right; }\n'
    #msg += '</style>'
    msg += inmsg
    #msg += '\n</div>\n'
    return msg

if __name__ == '__main__':
    app.run(ssl_context=('/home/descprod/cert.pem', 'key.pem'))
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(minutes=5)
if 'SERVER_OPTS' in os.environ:
    opts=os.environ['SERVER_OPTS'].split()
    for opt in opts:
        fprint(f"Processing server option {opt}")
        if opt == 'debug':
            SessionData.dbg = True
        elif opt == 'force-https':
            SessionData.force_https = True
        else:
            fprint(f"Ignoring invalid option {opt}")

def get_jobid():
    fnam  = '/home/descprod/local/etc/jobid.txt'
    jobid = int(subprocess.getoutput(f"descprod-next-jobid"))
    return jobid

def get_sessionid():
    lines = subprocess.getoutput(f"descprod-next-sessionid").splitlines()
    sesid = int(lines[-1])
    for line in lines[0:-1]:
        fprint(f"get_sessionid: {line}")
    if SessionData.dbg: fprint(f"get-sessionid: Session ID is {sesid}")
    return sesid

@app.route("/")
def top():
    return home();
    #return redirect(url_for('home'))

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
    req_sesskey = request.args.get('sesskey')
    if req_sesskey is not None:
        sdat = SessionData.get(req_sesskey)
        # Strip sesskey from the URL.
        resp = sdat.make_response(redirect(request.base_url))
        return resp
    sdat = SessionData.get(req_sesskey)
    msg = 'home: Constructing home page for '
    if req_sesskey is not None: msg += 'new '
    if req_sesskey is None: msg += 'existing '
    msg += f"session {sdat.session_id}."
    if SessionData.dbg: fprint(msg)
    sep = '<br>\n'
    msg = html_head()
    msg += '<h2>DESCprod</h2>\n'
    udat = sdat.user()
    if SessionData.dbg: fprint(f"home: User is {sdat.user()} [id: {sdat.session_id}, key: {sdat.sesskey}]")
    have_user = sdat.sesskey is not None
    if have_user and sdat.refresh.focus:
        # Refresh page each time listener selects browser tab.
        msg += '<script>\n'
        msg += 'document.addEventListener("visibilitychange", () => {\n'
        msg += '    if ( ! document.hidden ){\n'
        msg += '        location.reload()\n'
        msg += '    }\n'
        msg += '});\n'
        msg += '</script>\n'
    if have_user and sdat.refresh.period():
        msg += '<script>\n'
        msg += f'setTimeout(() => location.reload(), {1000*sdat.refresh.period()});\n'
        msg += '</script>\n'
    if have_user or True:
        if len(sdat.msg):
            if isinstance(sdat.msg, list):
                lines = sdat.msg
            else:
                lines = [str(sdat.msg)]
            msg += f"<hr>\n"
            msg += f"<pre>\n"
            lsep = ''
            for line in lines:
                msg += f"{lsep}{line}"
                lsep = '\n'
            msg += f"\n</pre>\n"
            msg += f"<hr>{sep}"
            sdat.msg = []
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
        msg += sep
        msg += f"UTC time: {sdate()}"
        #msg += f" [{sdat.sesskey}]"
        msg += sep
        msg += f"Refresh period: {sdat.refresh.period_label()}"
        msg += sep
        msg += sep
        jtab = JobTable(udat.descname)
        if (jtab.error_message):
              msg += f"ERROR: {jtab.error_message}"
              return sdat.make_response(msg)
        # Use the last job to to get the starting job config if it is not already set.
        if udat.jobtype == '':
            jids = list(jtab.jobs.keys())
            if len(jids):
                jids.sort()
                jid_last = jids[-1]
                job_last = jtab.jobs[jid_last]
                udat.jobtype = job_last.jobtype()
                udat.config = job_last.config()
                udat.howfig = job_last.howfig()
        njob = len(jtab.jobs)
        msg += f"User {udat.descname} has {njob} active job"
        if njob != 1: msg += 's'
        if njob:
            msg += ':'
            msg += sep
            msg += table_wrap(jtab.to_html(fixurl(request.base_url)[0:-5]))
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
        msg += f'''\n<form action="/form_create_job" method='POST'>Create job: '''
        msg += f'''<input type="text" name="jobtype" value="{udat.jobtype}" style="width: 150px;" />'''
        msg += f'''<input type="text" name="config"  value="{udat.config}"  style="width: 300px;" />'''
        msg += f'''<input type="text" name="howfig"  value="{udat.howfig}"  style="width: 300px;" />'''
        msg += f'<input type="submit" value="Submit"/></form>'''
        msg += sep
        msg += '<form action="/" method="get"><input type="submit" value="Refresh"></form>\n'
        msg += '<form action="/logout" method="get"><input type="submit" value="Log out"></form>\n'
        msg += '<form action="/versions" method="get"><input type="submit" value="Versions"></form>\n'
        msg += f'''<form action="/refresh_focus" method="get"><input type="submit" value="{sdat.refresh.focus_button_label()}"></form>\n'''
        msg += f'''<form action="/refresh_period" method="get"><input type="submit" value="Change refresh period"></form>\n'''
        #msg += '<form action="/session" method="get"><input type="submit" value="Show session"></form>'
        msg += '<form action="/pmstatus" method="get"><input type="submit" value="Perlmutter status"></form>\n'
        if udat.is_admin(): msg += '<form action="/bye" method="get"><input type="submit" value="Restart server"></form>\n'
    else:
        msg += sep
        msg += '<form action="/login" method="get"><input type="submit" value="Log in with google"></form>'
    msg += '<br><form action="/help" method="get"><input type="submit" value="Help"></form>'
    return sdat.make_response(msg)

@app.route("/login")
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri = fixurl(request.base_url) + "/callback"
    # For anything but local host, make sure redirect is https.
    if redirect_uri[0:5] == 'http:' and redirect_uri.find('localhost') < 0 and redirect_uri.find('127.0.0.1') < 0:
        redirect_uri = redirect_uri.replace('http:', 'https:')
    if SessionData.dbg: fprint(f"login: URI: {redirect_uri}")
    scope=["openid", "email", "profile"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=scope
    )
    if SessionData.dbg: fprint(f"login: Auth: {authorization_endpoint}")
    if SessionData.dbg: fprint(f"login: Request: {request_uri}")
    res = redirect(request_uri)
    if SessionData.dbg: fprint(f"login: Result: {res}")
    return res

@app.route("/logout")
def logout():
    sdat = SessionData.get()
    if sdat is None:
        fprint('logout: Logout requested without login. Might be expired.')
    else:
        fprint(f"logout: Logging out user {sdat.user().descname}.")
        del SessionData.sessions[sdat.sesskey]
    #session['sesskey'] = None
    sdat = sdat.logout()
    #resp = redirect(url_for('home'))
    #resp.set_cookie('sesskey', '', expires=0)
    return sdat.make_reponse()

@app.route("/help")
def help():
    return render_template('help.html')

@app.route("/bye")
def bye():
    fprint("bye: Shutting down.")
    com = f"sleep 3; kill -9 {os.getpid()}"
    subprocess.Popen(com, shell=True)
    sdat = SessionData.get()
    sdat.msg += ['Restarting server.']
    return redirect(url_for('home'))

@app.route("/login/callback")
def callback():
    if SessionData.dbg: fprint('callback: Handling google callback')
    # Fetch tokens.
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    if request.is_secure:
        authresp = fixurl(request.url)
    else:
        authresp = None
    fprint(f"callback: **************** authresp: {authresp}")
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
        fprint('callback: --------- END Token response')
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
        fprint('callback: --------- END Token response')
    # Parse tokens and fetch user profile.
    client.parse_request_body_response(json.dumps(resp))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    login_info = userinfo_response.json()
    google_id      = login_info["sub"]
    fullname    = login_info["name"]
    user_label = f"{fullname} ({google_id})"
    #fprint(f"callback: User info: {login_info")
    resp = redirect(url_for('home'))
    sdat = SessionData.nologin_session()
    sesskey = None
    email = userinfo_response.json().get("email")
    have_email = len(email) > 0
    email_verified = userinfo_response.json().get("email_verified")
    # 06jan2023  Allow unverified email.
    verified = email_verified or have_email
    if verified:
        if google_id in SessionData.google_ids:
            fprint(f"callback: Authorizing  {user_label}")
            login_info    = userinfo_response.json()
            if SessionData.use_cookie_key:
                # The cookie is created in sdat.make_response
                # We need a string key.
                sesskey = make_session_key()
            else:
                sesskey = app.secret_key = os.urandom(16)
                session['sesskey'] = sesskey
                session['fullname'] = fullname
                session.permanent = True   # This enables the session to expire
            descname = SessionData.google_ids[google_id][0]
        else:
            fprint(f"callback: Denying unauthorized user {user_label} [{email}]")
            sdat.msg.append(f"User not authorized: {google_id} {fullname}")
            sdat.msg.append(f"\n<br>Send the above line and your NERSC user name to admin@descprod.org to request authorization.")
    else:
        fprint(f"callback: Denying unverified user {user_label} [{email}]")
        if not email_verified: sdat.msg.append(f"User has not verified email with google: {fullname} [{email}]")
        if not have_email: sdat.msg.append(f"User does not have email with google: {fullname} [{google_id}]")
    unam = url_for('home')
    if sesskey is not None:
        arg_sesskey = make_session_key()
        sdat = SessionData(sesskey, descname, fullname, login_info)
        SessionData.arg_session_dict[arg_sesskey] = sesskey
        if not SessionData.use_cookie_key:
            session['session_id'] = sdat.session_id
        unam += f"?sesskey={arg_sesskey}"
    return redirect(unam)

@app.route("/versions")
def versions():
    #return f"{os.getcwd()}<br>{__file__}"
    sep = '<br>\n'
    tbl = {}
    tbl['Python'] = subprocess.getoutput('echo $(python --version)')
    tbl['desc-prod'] = subprocess.getoutput('descprod-version')
    wprod = 0
    for prod in tbl:
        wprod = max(wprod, len(prod))
    outmsg = []
    for prod in tbl:
        outmsg += [f"{prod.rjust(wprod+4)}: {tbl[prod]}"]
    SessionData.get().msg = outmsg
    return redirect(url_for('home'))

@app.route("/refresh_focus")
def refresh_focus():
    sdat = SessionData.get()
    sdat.refresh.change_focus()
    return redirect(url_for('home'))

@app.route("/refresh_period")
def refresh_period():
    sdat = SessionData.get()
    sdat.refresh.increment_period()
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
        sdat.msg = ["<h1>Hellos from desc-prod</h1>"]
    sdat.msg += [f"hello{name}</br>"]
    return redirect(url_for('home'))

@app.route('/form_create_job/', methods=['POST', 'GET'])
def run_form_create_job():
    if request.method == 'GET':
        return 'Got GET instead of POST!!'
    sdat = SessionData.get()
    jty = request.form['jobtype'].strip()
    #known_jty = ['parsltest']
    #if jty not in known_jty:
    #    SessionData.get().msg.append(f"Invalid job type: {jty}")
    #    return redirect(url_for('home'))
    cfg = request.form['config'].strip()
    hfg = request.form['howfig'].strip()
    fprint(f"form_create_job: {jty} {cfg} {hfg}")
    return do_create_job(jty, cfg, hfg)

def do_create_job(jty, cfg, hfg):
    myname = 'do_create_job'
    sdat = SessionData.get()
    if len(cfg) == 0:
        sdat.msg.append('Configuration must be provided when creating a job.')
        return redirect(url_for('home'))
    sid = sdat.session_id
    udat = sdat.user()
    if udat.descname == 'nologin':
        sdat.msg.append('Log in to make a job request')
        return redirect(url_for('home'))
    jobid = get_jobid()
    jdat = JobData(jobid, udat.descname)
    if len(jdat.errmsgs):
        sdat.msg.append(jdat.errmsgs)
        return redirect(url_for('home'))
    if jdat.configure(jty, cfg, hfg, sid):
        sdat.msg += jdat.errmsgs
        return redirect(url_for('home'))
    sdat.msg.append(f"Configured {jty} {cfg} {hfg}")
    udat.jobtype = jty
    udat.config = cfg
    udat.howfig = hfg
    return redirect(url_for('home'))

@app.route('/startjob')
def start_job():
    sdat = SessionData.get()
    udat = sdat.user()
    if udat.descname == 'nologin':
        sdat.msg.append('Log in to start a job')
        return redirect(url_for('home'))
    jobid = int(request.args['id'])
    job = JobData.get_user_job(udat.descname, jobid)
    if job is None:
        sdat.msg.append(f"Job {jobid} not found for user {udat.descname}")
        return redirect(url_for('home'))
    cmsg = job.ready_to_run()
    if len(cmsg):
        sdat.msg.append(f"Job {jobid} is not ready to run. {cmsg}")
        return redirect(url_for('home'))
    if job.run():
        sdat.msg = job.errmsgs
        return redirect(url_for('home'))
    sdat.msg.append(f"Started job {jobid} for user {job.descname()} in {job.rundir()}")
    return redirect(url_for('home'))

@app.route('/archivejob')
def archive_job():
    sdat = SessionData.get()
    udat = sdat.user()
    if udat.descname == 'nologin':
        sdat.msg.append('Log in to archive a job')
        return redirect(url_for('home'))
    jobid = int(request.args['id'])
    job = JobData.get_user_job(udat.descname, jobid)
    if job is None:
        sdat.msg.append(f"Job {jobid} not found for user {udat.descname}")
    else:
        arcfil = job.archive()
        if arcfil is None:
            sdat.msg.append(f"Unable to archive Job {jobid} for user {udat.descname}")
        else:
            sdat.msg.append(f"Job archived at {arcfil}")
    return redirect(url_for('home'))

@app.route('/deletejob')
def delete_job():
    sdat = SessionData.get()
    udat = sdat.user()
    if udat.descname == 'nologin':
        sdat.msg.append('Log in to delete a job')
        return redirect(url_for('home'))
    jobid = int(request.args['id'])
    job = JobData.get_user_job(udat.descname, jobid)
    if job is None:
        sdat.msg.append(f"Job {jobid} not found for user {udat.descname}")
    else:
        delfil = job.delete()
        if delfil is not None:
            sdat.msg.append(f"Job {jobid} scheduled for deletion at {delfil}")
    return redirect(url_for('home'))

@app.route('/copyjob')
def copy_job():
    sdat = SessionData.get()
    udat = sdat.user()
    if udat.descname == 'nologin':
        sdat.msg.append('Log in to delete a job')
        return redirect(url_for('home'))
    jobid = int(request.args['id'])
    job = JobData.get_user_job(udat.descname, jobid)
    if job is None:
        sdat.msg.append(f"Job {jobid} not found for user {udat.descname}")
    else:
        udat.jobtype = job.jobtype()
        udat.config = job.config()
        udat.howfig = job.howfig()
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
    fprint(session)
    msg = 'Session data:\n'
    for key in session.keys():
        msg += f"<br>{key}: {session[key]}\n"
    fprint(msg)
    SessionData.get().msg = msg
    return redirect(url_for('home'))

@app.route("/request")
@app.route("/<path:path>")
def req(path):
    sdat = SessionData.get()
    sdat.msg.append(f"Invalid command: {request.url}")
    fprint(f"req: Ignoring request {request.url}")
    return redirect(url_for('home'))
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

@app.route('/favicon.ico')
def got_favicon():
    fprint(f"got_favicon: Ignoring request {request.url}")
    return {}

@app.route('/get_job', methods=['POST'])
def get_job():
    """Handle request to return a job."""
    rst = 0
    msg = 'Success.'
    rec = request.json
    missingkeys = []
    for key in ['descname', 'id']:
        if key not in rec: missingkeys += [key]
    if len(missingkeys):
        return {'status':1, 'message':f"Missing keys in request: {missingkeys}"}
    jid = int(rec['id'])
    descname = rec['descname']
    job = JobData.get_user_job(descname, jid, usedb=True)
    if job is None:
        return {'status':2, 'message':f"Job {jid} not found for user {descname}."}
    jmap = job.jmap()
    return {'status':0, 'message':'Success', 'job':jmap}

@app.route('/update_job', methods=['POST', 'GET'])
def update_job():
    """Handle request to update a job."""
    if request.method == 'GET':
        return 'Got GET instead of POST!!'
    rec = request.json
    if 'job' not in rec: return {'status':1, 'message':'Request does not include job'}
    jmap = rec['job']
    for nam in ['id', 'descname', 'update_time']:
        if nam not in jmap: return {'status':2, 'message':f"Request job does not have field {nam}"}
        if jmap[nam] is None: return {'status':3, 'message':f"Request job does not have a value for field {nam}"}
    jid = jmap['id']
    descname = jmap['descname']
    job = JobData.get_user_job(descname, jid, usedb=True)
    if job is None:
        otim = 0
    else:
        otim = job.update_time()
        if otim is None:
            otim = 0
            fprint(f"update_job: WARNING: Handling job {descname}/{jid} with missing update time.")
    utim = jmap['update_time']
    try:
        dtim = utim - otim
    except:
        return {'status':4, 'message':f"Invalid time interval: {utim} - {otim}"}
    if job is None: return {'status':5, 'message':f"Job {jid} not found for user {descname}"}
    if dtim <= 0: return {'status':6, 'message':f"Job {descname}/{jid}: Update is {-dtim} seconds behind current job."}
    errmsg = job.jmap_update(jmap)
    if len(errmsg): return {'status':5, 'message':f"Job {descname}/{jid}: {errmsg}"}
    return {'status':0}

@app.route('/add_child_job', methods=['POST', 'GET'])
def add_child_job():
    """Handle request to add a job."""
    if request.method == 'GET':
        return 'Got GET instead of POST!!'
    jmap = request.json
    for nam in ['jobtype', 'config', 'parent', 'descname']:
        if nam not in jmap:   return {'status':1, 'message':f"Request to add child job does not have field {nam}"}
        if jmap[nam] is None: return {'status':2, 'message':f"Request to add child job does not have a value for field {nam}"}
    jobtype = jmap['jobtype']
    cfg = jmap['config']
    hfg = jmap['howfig']
    parent = int(jmap['parent'])
    descname = jmap['descname']
    # Require parent has the same username.
    pjob = JobData.get_user_job(descname, parent, usedb=True)
    if pjob is None:
        return {'status':3, 'message':f"Parent job {descname}/{parent} was not found"}
    sid = pjob.session()
    jid = get_jobid()
    jdat = JobData(jid, descname)
    if jdat.configure(jobtype, cfg, hfg, sid, parent):
        return {'status':4, 'message':jdat.errmsgs[-1]}
    fprint(f"add_child_job: Added and configured child job {descname}/{jid}: {jobtype} {cfg}")
    return {'status':0, 'job':jdat.jmap()}
