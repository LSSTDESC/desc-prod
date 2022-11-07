from flask import Flask

app = Flask(__name__)

class Msg:
    msg = ''

@app.route("/help")
def help():
    msg = '<H1>Hello help</H1>'
    msg += '<br> help - This message.'
    msg += '<br> bye - Clears page.'
    msg += '<br> hello/John - Says hello to John'
    msg += '<br> hello/John - Says hello to John'
    msg += '<br> hello/John?Doe - Says hello to John Doe'
    return msg

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

