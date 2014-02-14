#!/usr/bin/env python
import sys, os, struct, getopt, subprocess, signal
from subprocess import PIPE
from bup import options, ssh, path
from bup.helpers import *

optspec = """
bup on <hostname> index ...
bup on <hostname> save ...
bup on <hostname> split ...
"""
o = options.Options(optspec, optfunc=getopt.getopt)
(opt, flags, extra) = o.parse(sys.argv[1:])
if len(extra) < 2:
    o.fatal('arguments expected')

class SigException(Exception):
    def __init__(self, signum):
        self.signum = signum
        Exception.__init__(self, 'signal %d received' % signum)
def handler(signum, frame):
    raise SigException(signum)

signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGINT, handler)

sp = None
p = None
ret = 99

try:
    hp = extra[0].split(':')
    if len(hp) == 1:
        (hostname, port) = (hp[0], None)
    else:
        (hostname, port) = hp

    argv = extra[1:]
    p = ssh.connect(hostname, port, 'on--server', stderr=PIPE)

    argvs = '\0'.join(['bup'] + argv)
    p.stdin.write(struct.pack('!I', len(argvs)) + argvs)
    p.stdin.flush()

    sp = subprocess.Popen([path.exe(), 'server'],
                          stdin=p.stdout, stdout=p.stdin)
    p.stdin.close()
    p.stdout.close()

finally:

    # Demultiplex remote client's stderr (back to stdout/stderr).
    for line in iter(p.stderr.readline, ""):
        sys.stdout.flush()
        sys.stderr.flush()
        if line.startswith('on '):
            sys.stdout.write(line[3:])
        elif line.startswith('o_ '):
            sys.stdout.write(line[3:-1])
        elif line.startswith('en '):
            sys.stderr.write(line[3:])
        elif line.startswith('e_ '):
            sys.stderr.write(line[3:-1])
        else:
            log('bad redirection prefix in %r\n' % line)

    while 1:
        # if we get a signal while waiting, we have to keep waiting, just
        # in case our child doesn't die.
        try:
            ret = p.wait()
            sp.wait()
            break
        except SigException, e:
            log('\nbup on: %s\n' % e)
            os.kill(p.pid, e.signum)
            ret = 84
sys.exit(ret)