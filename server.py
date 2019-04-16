#! python3

import os

import binascii
import string
import random

import flask
from flask import request, session

import db

app = flask.Flask(__name__)
app.secret_key = "key"

@app.route('/', methods=['GET', 'POST'])
def home():
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
    if request.method == 'POST':
        user = db.User.login(request.form['username'], request.form['password'])
        if user:
            session['username'] = user.username
            session['user_id'] = user.id
            return flask.redirect(flask.url_for('home'))
        return

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return flask.redirect(flask.url_for('home'))

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'username' not in session:
        flask.flash('you are not logged in')
        return flask.redirect('/login')
    if request.method == 'GET':
        user = db.session.query(db.User).filter(db.User.username == session['username']).first()
        return flask.render_template('account.html', upload_key=user.upload_key)
    if request.method == 'POST':
        user = db.session.query(db.User).filter(db.User.username == session['username']).first()
        if 'regenerate_upload_key' in request.form:
            user.upload_key = db.User.gen_upload_key()
            db.session.commit()
            return flask.redirect(flask.url_for('account'))

        if 'update_password' in request.form:
            if user.password != db.User.hash_pw(request.form['current_password'], binascii.unhexlify(user.salt))[0]:
                flask.flash('current password incorrect')
                return flask.redirect(flask.url_for('account'))
            if request.form['new_password'] != request.form['confirm_new_password']:
                flask.flash('new passwords do not match')
                return flask.redirect(flask.url_for('account'))
            user.password = db.User.hash_pw(request.form['new_password'], binascii.unhexlify(user.salt))[0]
            db.session.commit()
            return flask.redirect(flask.url_for('account'))
    return flask.render_template('account.html')

if __name__ == '__main__':
    app.run()
