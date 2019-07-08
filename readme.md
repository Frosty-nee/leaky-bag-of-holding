## leaky-bag-of-holding
An ephemeral file sharing solution with automatic file deletion. Files are deleted on a first in first out basis.


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

## Config Setup:
`mv config.py.example config.py`

`max_content_length` and `max_usable_disk_space` are a number of bytes (defaults are 1MB and 5GB)

`files_domain` is the domain that you're using to actually serve the files that are uploaded


## User Management:

```
./db.py create username password
./db.py delete username
```


## Nginx setup:
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

