from flask import Flask

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/")
def hello():
    return "<h1>Hellos from desc-prod</h1>"

@app.route("/hello/<username>")
def hello_hello(username):
    if len(username) == 0:
        Msg.msg = "<h1>Hellos from desc-prod</h1>"
    else:
        Msg.msg += f"hello {username}</br>"
    return Msg.msg

