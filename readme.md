## leaky-bag-of-holding
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
./db.py init
```
## User Management:

```
./db.py create username password
./db.py delete username
```


## Webserver setup:
You'll need to set up two configs, one which is hosting the files and one which is serving the actual website.
#### webserver sample config:
````
server {
  server_name web.server.domain;
  client_max_body_size 100M;
  
  root /file/path/to/your/project/;
  
  location / {
    include proxy_params;
    proxy_pass https://127.0.0.1:5000/;
  }
}
````
#### File host sample config:
```
server {
  server_name file.host.domain;
  root /path/to/the/project/uploads/;
  
  location / {
    try_files $uri @dev;
  }
  
  location @dev {
    return 302 https://web.server.domain;
  }
  
  location /favicon.ico {
    return 302 https://web.server.domain/static/favicon.png
  }
}
```

