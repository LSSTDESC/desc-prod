from flask import Flask

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/bye")
def bye():
    Msg.msg = ''
    return ""

@app.route("/hello/<username>")
def hello_hello(username):
    if len(Msg.msg) == 0:
        Msg.msg = "<h1>Hellos from desc-prod</h1>"
    Msg.msg += f"hello {username}</br>"
    return Msg.msg

