from datetime import datetime
from flask import Flask
from flask import request
from markupsafe import escape
import sys
inport os

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/help")
def help():
    msg = '<H1>Hello help</H1>'
    msg +=      '          help - This message.'
    msg += '<br>            bye - Clears page.'
    msg += '<br>     hello?John - Says hello to John'
    msg += '<br> hello?John&Doe - Says hello to John Doe'
    msg += '<br>        request - Parses a request'
    return msg

@app.route("/bye")
def bye():
    print("Shutting down.")
    os.kill(os.pid(), 9)
    return ""

@app.route("/restart")
def restart():
    msg = str(datetime.now)
    fout = open('/home/descprod/restart', 'a')
    fout.write(msg)
    fout.close()
    return "Restarting server."

@app.route("/hello")
def hello():
    name = ''
    if len(request.args):
        for snam in request.args:
            name += ' ' + snam
    else:
        name = ' NOONE'
    if len(Msg.msg) == 0:
        Msg.msg = "<h1>Hellos from desc-prod</h1>"
    Msg.msg += f"hello{name}</br>"
    return Msg.msg

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
