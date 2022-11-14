from datetime import datetime
from flask import Flask
from flask import request
from markupsafe import escape
import sys
import os
import subprocess

app = Flask(__name__)

class Data:
    msg = ''
    fnam = '/home/descprod/job.log'
    fout = None
    sjob = None
    ret = None
    njob = 0
    def current_jobid():
        if njob: return njob-1
        return None

@app.route("/help")
def help():
    msg = '<H1>Hello help</H1>'
    msg +=      '          help - This message.'
    msg += '<br>            bye - Restarts the server.'
    msg += '<br>     hello?John - Says hello to John'
    msg += '<br> hello?John&Doe - Says hello to John Doe'
    msg += '<br>        request - Parses a request'
    msg += '<br>      parsltest - Parses a request'
    return msg

@app.route("/bye")
def bye():
    print("Shutting down.")
    os.kill(os.getpid(), 9)
    return ""

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
    fout = Data.fout
    if Data.sjob is not None and Data.ret is None:
        return f"Job is already running: {sjob}"
    Data.sjob = args
    if Data.ret is not None:
        rcode = Data.ret.poll()
        if rcode is None:
            msg = f"Earlier job {Data.sjob} is still running."
            return msg
        Data.ret = None
    com = ['desc-wfmon-parsltest', args]
    if fout is not None:
        fout.close() 
    print(f"{myname}: Opening {Data.fnam}")
    fout = open(Data.fnam, 'w')
    Data.ret = subprocess.Popen(com, stdout=fout, stderr=fout)
    return f"Started {com[0]} {com[1]}"

@app.route('/status')
def status():
    if Data.sjob is None:
        msg = "No job is started."
    else:
        rcode = Data.ret.poll()
        if rcode is None:
            msg = f"Job {Data.sjob} is running."
        else:
            msg = f"Job {Data.sjob} returned {rcode}."
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

