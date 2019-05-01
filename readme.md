##leaky-bag-of-holding
an ephemeral file sharing solution with automatic file deletion after a specified delay


## Database Setup:

```
$ sudo -u postgres -i
$ psql
```
```
# create database boh;
# create user boh;
# grant all privileges on database boh to boh;
```

Create the db schema by running:
```
$ python -c "import db; db.init_db();"
```

## Webserver setup:
TBD


