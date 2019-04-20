#! python3

import os
import binascii
import string
import random
from datetime import datetime, timedelta
import threading
import time

import flask
from flask import request, session

import db
import config

app = flask.Flask(__name__)
app.secret_key = config.secret_key

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'username' not in session:
            user = None
        else:
            user = db.session.query(db.User).filter(db.User.username == session['username']).first()
        return flask.redirect(upload_file(user, request.files, request.form.get('expire_in')))
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
        flask.flash('login unsuccessful')
        return flask.redirect(flask.url_for('login'))


'''
route for sharex use, takes url parameters 'upload_key' and 'expires'
upload key is copy/pasted from account page
expires is a string in the format 1d2h3m
'''
@app.route('/upload', methods=['POST'])
def upload():
    user = db.session.query(db.User).filter(db.User.upload_key == request.args.get('upload_key')).first()
    expires = request.args.get('expires')
    return upload_file(user, request.files, expires)

'''
takes a duration string and converts it to timedelta
string format is 1d2h3m
'''
def parse_time(expiry_string):
    td_args = {'days': 0, 'hours': 0, 'minutes': 0}
    for char, unit in zip('dhm', ['days', 'hours', 'minutes']):
        try:
            n_units, arg = expiry_string.split(char,1)
        except ValueError:
            continue
        try:
            td_args[unit] = int(n_units)
        except ValueError as e:
            continue
    try:
        td = timedelta(**td_args)
    except OverflowError:
        return flask.abort(400)
    return td

def upload_file(user, files, expires=None):
    if expires == None:
        expires = '7d'
    expires = parse_time(expires) + datetime.utcnow()
    if user == None:
        return flask.abort(401)
    else:
        for f in files:
            file_extension = os.path.splitext(files[f].filename)[1]
            while True:
                random_filename = ''.join([random.choice(string.ascii_lowercase + string.digits) for n in range(12)]) + file_extension
                if check_filename_free(random_filename):
                    break
            files[f].save(os.path.join('uploads/', random_filename))
            db.session.add(db.File(who_uploaded=user.id, filename=random_filename, expires=expires))
            db.session.commit()
            return 'https://file.frosty-nee.net/' + random_filename

def check_filename_free(filename):
    if db.session.query(db.File).filter(db.File.filename == filename).first() == None:
        return True
    else:
        return False

@app.route('/delete/<filename>')
def delete(filename):
    if request.args.get('upload_key') == None and 'username' not in session:
        return flask.abort(401)
    else:
        f = db.session.query(db.File).filter(db.File.filename == filename).first()
        if 'user_id' in session:
            user_id = session['user_id']
        else:
            user_id = db.session.query(db.User).filter(db.User.upload_key == request.args.get('upload_key')).first()
        if f.who_uploaded == user_id:
            try:
                os.remove(os.path.join('uploads/', f.filename))
                db.session.delete(f)
            except OSError as e:
                return flask.abort(500)
            db.session.commit()
    return flask.redirect(flask.url_for('account'))


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
        files = db.session.query(db.File).filter(db.File.who_uploaded == user.id)
        return flask.render_template('account.html', upload_key=user.upload_key, files=files)

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

def delete_expired():
    while True:
        files = db.session.query(db.File).filter(db.File.expires <= datetime.utcnow())
        for f in files:
            try:
                os.remove(os.path.join('uploads/', f.filename))
                db.session.delete(f)
            except OSError as e:
                pass
        db.session.commit()
        time.sleep(60)


if __name__ == '__main__':
    delete_thread = threading.Thread(target=delete_expired)
    delete_thread.start()
    app.run(port=config.port, debug=config.debug)

