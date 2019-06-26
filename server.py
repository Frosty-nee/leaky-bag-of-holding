#! python3
import eventlet
eventlet.monkey_patch()

import os
import binascii
import string
import random
from datetime import datetime, timedelta
import threading
import time

import flask
from flask import request, session
from werkzeug.utils import secure_filename
import eventlet.wsgi

import db
import config

app = flask.Flask(__name__)
app.secret_key = config.secret_key
app.config['MAX_CONTENT_LENGTH'] = config.max_content_length

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'username' not in session:
            user = None
        else:
            user = get_user(username=session['username'])
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
    user = get_user(upload_key=request.args.get('upload_key'))
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

def get_current_disk_usage():
    return sum(os.path.getsize(os.path.join('uploads', f)) for f in os.listdir('uploads'))

def make_space_on_disk(incoming_filesize):
    for f in db.session.query(db.File).order_by(db.File.expires).all():
        if incoming_filesize + get_current_disk_usage() < config.max_usable_disk_space:
            break
        delete_file(f)

def upload_file(user, files, expires=None):
    uploaded_size = 0
    current_disk_usage = get_current_disk_usage()
    for f in files:
        files[f].seek(0,os.SEEK_END)
        uploaded_size += files[f].tell()
        files[f].seek(0)
    if uploaded_size + current_disk_usage >= config.max_usable_disk_space:
        make_space_on_disk(uploaded_size)
    if expires == None:
        expires = '7d'
    expires = parse_time(expires) + datetime.utcnow()
    if user == None:
        return flask.abort(401)
    else:
        for f in files:
            file_extension = os.path.splitext(secure_filename(files[f].filename))[1]
            while True:
                random_filename = ''.join([random.choice(string.ascii_lowercase + string.digits) for n in range(13)]) + file_extension
                if check_filename_free(random_filename):
                    break
            files[f].save(os.path.join('uploads/', random_filename))
            db.session.add(db.File(who_uploaded=user.id, filename=random_filename, expires=expires))
            db.session.commit()
            return 'https://{}/'.format(config.files_domain) + random_filename

def check_filename_free(filename):
    if not get_file(filename):
        return True
    else:
        return False

@app.route('/delete/<filename>')
def delete(filename):
    if not request.args.get('upload_key') and 'username' not in session:
        return flask.abort(401)
    else:
        if 'user_id' in session:
            user_id = session['user_id']
        elif request.args.get('upload_key'):
            user_id = get_user(upload_key=request.args.get('upload_key')).id
        else:
            return flask.abort(401)
        f = get_file(filename)
        if not f:
            return flask.abort(500)
        if f.who_uploaded == user_id:
            try:
                delete_file(f)
            except OSError:
                return flask.abort(500)
    return flask.redirect(flask.url_for('account'))

def delete_file(f):
    try:
        db.session.delete(f)
        db.session.commit()
        os.remove(os.path.join('uploads/', f.filename))
    except OSError:
        raise


def get_file(filename):
    return db.session.query(db.File).filter(db.File.filename == filename).one_or_none()

def get_user(username=None, user_id=None, upload_key=None):
    if username:
        user_query =  db.session.query(db.User).filter(db.User.username == username)
    elif user_id:
        user_query = db.session.query(db.User).filter(db.User.id == user_id)
    elif upload_key:
        user_query = db.session.query(db.User).filter(db.User.upload_key == upload_key)
    else:
        raise AssertionError("get_user called with no identifier")
    return user_query.one_or_none()

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
        user = get_user(username=session['username'])
        files = db.session.query(db.File).filter(db.File.who_uploaded == user.id)
        return flask.render_template('account.html', upload_key=user.upload_key, files=files)

    if request.method == 'POST':
        user = get_user(username=session['username'])
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
    if config.debug:
        app.run(port=config.port, debug=config.debug)
    else:
        listener = eventlet.listen((config.web_host, config.web_port))
        eventlet.wsgi.server(listener, app)
