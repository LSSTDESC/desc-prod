from flask import Flask

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/")
def hello():
    return "<h1>Hello again from desc-prod</h1>"

@app.route("/hello")
def hello_hello():
    Msg.msg += 'hello '
    return Msg.msg

