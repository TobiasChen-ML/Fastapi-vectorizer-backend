# from config import BIND,WORKERS,THREADS,PIDFILE,ACCESSLOG,ERRORLOG,TIMEOUT

bind = "0.0.0.0:7999"
workers = 2
threads = 1
backlog = 2048
worker_class = "gthread"
worker_connections = 10000
daemon = True
timeout = 240000
pidfile = 'log/gunicorn.pid'
accesslog = 'log/access.log'
errorlog = 'log/gunicorn.log'


# bind = BIND
# workers = WORKERS
# threads = THREADS
# backlog = 2048
# worker_class = "gthread"
# worker_connections = 10000
# daemon = True
# timeout = TIMEOUT
# pidfile = PIDFILE
# accesslog = ACCESSLOG
# errorlog = ERRORLOG