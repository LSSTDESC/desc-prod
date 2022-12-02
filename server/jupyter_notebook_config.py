# Install at .jupyter/jupyter_notebook_config.py
c = get_config()  # noqa
c.NotebookApp.password = 'argon2:$argon2id$v=19$m=10240,t=10,p=8$a2NyuxekzgeVmkcoDW7pTQ$SyvKJCZluG8febIx5l0DmetDerA8GyGcrCYIIYppBjA'
c.NotebookApp.allow_origin = '*' #allow all origins
c.NotebookApp.ip = '0.0.0.0' # listen on all IPs
