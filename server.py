#! python3

import os

import string
import random

import flask
from flask import request, session


app = flask.Flask(__name__)
app.secret_key = "key"

@app.route('/', methods=['GET', 'POST'])
def root():
    if request.method == 'POST':
        for f in request.files:
            file_extension = os.path.splitext(request.files[f].filename)[1]
            print(file_extension)
            random_filename = ''.join([random.choice(string.ascii_lowercase + string.digits) for n in range(12)]) + file_extension
            request.files[f].save(os.path.join('uploads/', random_filename))
        return 'https://file.frosty-nee.net/' + random_filename
    else:
        return flask.render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return flask.render_template('login.html')
    
    else:
        return
@app.route('/account')
def account():
    return flask.render_template('account.html')

if __name__ == '__main__':
    app.run()
