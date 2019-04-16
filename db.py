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
    username = Column(String)
    salt = Column(String)
    password = Column(String)
    upload_key = Column(String)

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
    
    

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    who_uploaded = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String)
    expires = Column(DateTime)

    def __repr__(self):
        return"<File(filename='%s', who_uploaded='%s', expires='%s')>" % (self.filename, self.who_uploaded, self.expires)

def init_db():
    Base.metadata.create_all(bind=engine)

def drop_db():
    pass

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'init':
            init_db()
        if sys.argv[1] == 'drop':
            drop_db()
        
