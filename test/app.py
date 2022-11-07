from flask import Flask
from flask import request
from markupsafe import escape

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/help")
def help():
    msg = '<H1>Hello help</H1>'
    msg +=      '          help - This message.'
    msg += '<br>            bye - Clears page.'
    msg += '<br>     hello/John - Says hello to John'
    msg += '<br> hello/John?Doe - Says hello to John Doe'
    return msg

@app.route("/bye")
def bye():
    Msg.msg = ''
    return ""

@app.route("/hello/<a_name>")
def hello(a_name):
    name = escape(a_name)
    if len(Msg.msg) == 0:
        Msg.msg = "<h1>Hellos from desc-prod</h1>"
    Msg.msg += f"hello {name}</br>"
    return Msg.msg

@app.route("/req")
def req():
    msg = ''
    msg += f"  gdat: {request.get_data().decode('UTF-8')}<br><br>"
    msg += f"  args: {request.args}<br><br>"
    msg += f"  form: {request.form}<br><br>"
    msg += f"  data: {request.data.decode('UTF-8')}<br><br>"
    return msg
