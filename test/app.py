from datetime import datetime
from flask import Flask, render_template
from flask import request
from markupsafe import escape
import sys
import os
import subprocess

app = Flask(__name__)

def get_jobid():
    fnam  = '/home/descprod/data/etc/jobid.txt'
    jobid = int(subprocess.getoutput(f"descprod-next-jobid"))
    return jobid

class Data:
    msg = ''
    site = subprocess.getoutput('cat /home/descprod/data/etc/site.txt')
    lognam = None
    logfil = None
    jobid = 0
    fout = None
    sjob = None
    rundir = None
    com = None
    ret = None
    def current_jobid():
        if njob: return njob-1
        return None

@app.route("/")
def home():
    #return render_template('index.html')
    sep = '<br>\n'
    msg = '<h2>DESCprod</h2>'
    msg += f"Site: {Data.site}"
    msg += sep
    msg += f"Status: {status()}"
    msg += sep
    msg += sep
    if ready():
        msg += f'''\nParsltest job: <form action="/form_parsltest" method='POST'><input type="text" name="config"/><input type="submit" value="Submit"/></form>'''
        msg += sep
    msg += '<form action="/bye" method="get"><input type="submit" value="Restart"></form>'
    msg += '<form action="/help" method="get"><input type="submit" value="Help"></form>'
    msg += '<form action="/versions" method="get"><input type="submit" value="Versions"></form>'
    return msg

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

@app.route("/versions")
def versions():
    sep = '<br>\n'
    msg = subprocess.getoutput('/home/descprod/dev/desc-prod/ptenv/ptenv-versions').replace('\n', sep)
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
        return f"Job is already running: {sjob}"
    if Data.ret is not None:
        rcode = Data.ret.poll()
        if rcode is None:
            msg = f"Earlier job {Data.sjob} is still running."
            return msg
        Data.ret = None
    sjobid = str(get_jobid())
    while len(sjobid) < 6: sjobid = '0' + sjobid
    Data.rundir = f"/home/workdir/data/rundirs/job{sjobid}"
    os.mkdir(rundir)
    Data.sjob = args
    Data.com = ['desc-wfmon-parsltest', args]
    if fout is not None:
        fout.close() 
    data.lognam = f"{rundir}/job{sjobid}.log"
    print(f"{myname}: Opening {Data.lognam}")
    Data.logfil = open(Data.lognam, 'w')
    Data.ret = subprocess.Popen(Data.com, cwd=Data.rundir, stdout=Data.logfil, stderr=Data.logfil)
    sep = '<br>\n'
    msg = f"Started {com[0]} {com[1]} in {Data.rundir}"
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
            msg = f"Job {Data.sjob} returned {Data.ret.poll()}."
        else:
            msg = f"Job {Data.sjob} is running."
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

