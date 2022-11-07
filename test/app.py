from flask import Flask

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/")
def hello():
    return "<h1>Hello again from desc-prod</h1>"

@app.route("/hello/<username>")
def hello_hello(username):
    Msg.msg += f"hello {username},"
    return Msg.msg

