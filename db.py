#! python3

import hashlib
import os
import string
import random
import binascii
from datetime import datetime


import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import backref, joinedload, relationship
from sqlalchemy.ext.declarative import declarative_base
import psycopg2

engine = sqlalchemy.create_engine(sqlalchemy.engine.url.URL(
    drivername='postgresql+psycopg2',
    username='boh',
    database='boh')
    )

session = sqlalchemy.orm.scoped_session(sqlalchemy.orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = session.query_property()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    salt = Column(String)
    password = Column(String)
    upload_key = Column(String, unique=True)

    def __repr__(self):
       return "<User(username='%s', password='%s', salt='%s')>" % (self.username, self.password, self.salt)

    @staticmethod
    def hash_pw(password, salt=None):
        if salt is None:
            salt = os.urandom(24)
        hashed = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000)
        hashed_hex = binascii.hexlify(hashed).decode()
        salt_hex = salt.hex()
        return hashed_hex, salt_hex

    @staticmethod
    def login(username, password):
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return False
        hashed, _ = User.hash_pw(password, binascii.unhexlify(user.salt))
        if hashed == user.password:
            return user

    @staticmethod
    def gen_upload_key():
        while True:
            key = binascii.hexlify(os.urandom(24)).decode()
            if session.query(User).filter(User.upload_key == key).count() > 0:
                continue
            else:
                return key

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    who_uploaded = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, unique=True)
    expires = Column(DateTime)

    def __repr__(self):
        return"<File(filename='%s', who_uploaded='%s', expires='%s')>" % (self.filename, self.who_uploaded, self.expires)

def init_db():
    Base.metadata.create_all(bind=engine)

def drop_db():
    Base.metadata.drop_all(bind=engine)


def create_user(username, password):
    hashed_pass, salt = User.hash_pw(password)
    upload_key = User.gen_upload_key()
    user = User(username=username, password=hashed_pass, salt=salt, upload_key=upload_key)
    session.add(user)

    try:
        session.commit()
    except sqlalchemy.exc.DBAPIError as e:
        print('Error:', e)

def delete_user(username):
    user = session.query(User).filter(User.username == username).first()
    files = session.query(File).filter(File.who_uploaded == user.id).all()
    for f in files:
        try:
            session.delete(f)
            session.commit()
            os.remove(os.path.join('uploads', f.filename))
        except OSError:
            pass
    session.delete(user)
    session.commit()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'init':
            init_db()
            sys.exit()
        if sys.argv[1] == 'drop':
            drop_db()
            sys.exit()
        if sys.argv[1] == 'create':
            create_user(sys.argv[2], sys.argv[3])
            sys.exit()
        if sys.argv[1] == 'delete':
            delete_user(sys.argv[2])
            sys.exit()
