#! python3
import eventlet
eventlet.monkey_patch()
import eventlet.wsgi

import os
import binascii
import string
import random
from datetime import datetime
import urllib.parse
import flask
from flask import request, session
from werkzeug.utils import secure_filename

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
            if 'keep_filename' in request.form:
                keep_filename=True
            else:
                keep_filename=False
            if not keep_filename: keep_filename=False
            print(keep_filename)
        return flask.redirect(upload_file(user, request.files, keep_filename))
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


@app.route('/upload', methods=['POST'])
def upload():
    '''
    route for sharex use, takes url parameters 'upload_key'
    upload key is copy/pasted from account page
    '''
    user = get_user(upload_key=request.args.get('upload_key'))
    if request.args.get('keep_filename') == "True":
        keep_filename=True
    else: keep_filename=False
    return upload_file(user, request.files, keep_filename)


def get_current_disk_usage():
    return sum(os.path.getsize(os.path.join('uploads', f)) for f in os.listdir('uploads'))

def make_space_on_disk(space_needed):
    space_cleared = 0
    for f in db.session.query(db.File).order_by(db.File.uploaded).all():
        if space_cleared > space_needed:
            break
        space_cleared += os.path.getsize(os.path.join('uploads', f.filename))
        delete_file(f)

def upload_file(user, files, keep_filename):
    uploaded_size = 0
    current_disk_usage = get_current_disk_usage()
    for f in files:
        files[f].seek(0, os.SEEK_END)
        uploaded_size += files[f].tell()
        files[f].seek(0)
    if uploaded_size + current_disk_usage >= config.max_usable_disk_space:
        make_space_on_disk(uploaded_size + current_disk_usage - config.max_usable_disk_space)
    if user is None:
        return flask.abort(401)
    for f in files:
        file_extension = os.path.splitext(secure_filename(files[f].filename))[1]
        if not keep_filename:
            while True:
                filename = ''.join([random.choice(string.ascii_lowercase + string.digits) for n in range(13)]) + file_extension
                if check_filename_free(filename):
                    break
        else:
            filename=files[f].filename
            if check_filename_free(filename):
                pass
            else:
                filename=handle_filename_collision(filename)

        files[f].save(os.path.join('uploads/', filename))
        filesize = os.path.getsize(os.path.join('uploads/', filename))
        db.session.add(db.File(who_uploaded=user.id, filename=filename, uploaded=datetime.utcnow(), filesize=filesize))
        db.session.commit()
        return 'https://{}/'.format(config.files_domain) + urllib.parse.quote(filename)

def handle_filename_collision(filename):
    filename, ext = os.path.splitext(filename)
    count=1
    while True:
        name = '{}_{}{}'.format(filename, count, ext)
        if check_filename_free(name):
            return name
        else:
            count+=1

def check_filename_free(filename):
    return not bool(get_file(filename))

@app.route('/delete/<filename>')
def delete(filename):
    if not request.args.get('upload_key') and 'username' not in session:
        return flask.abort(401)
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
        pass


def get_file(filename):
    return db.session.query(db.File).filter(db.File.filename == filename).one_or_none()

def get_user(username=None, user_id=None, upload_key=None):
    if username:
        user_query = db.session.query(db.User).filter(db.User.username == username)
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
        return flask.render_template('account.html', upload_key=user.upload_key, files=files, host=config.files_domain)

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
    return flask.render_template('account.html')


if __name__ == '__main__':
    if config.debug:
        app.run(port=config.port, debug=config.debug)
    else:
        listener = eventlet.listen((config.web_host, config.port))
        eventlet.wsgi.server(listener, app)
