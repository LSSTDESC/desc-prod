#!/usr/bin/env python3

import os
import sys
import time
import json
import requests
from authlib.integrations.requests_client import OAuth2Session
from authlib.oauth2.rfc7523 import PrivateKeyJWT

class Sfapi:
    _version = '1.0.3'
    _debug = 1
    _timeout = 10
    _sysname = 'perlmutter'
    _baseurl = "https://api.nersc.gov/api/v1.2"
    return_status = None
    session = None

    def  __init__(self, dbg=None, timeout=None, sysname=None, baseurl =None):
        if dbg is not None: set_debug(dbg)
        if timeout is not None: set_timeout(timeout)
        if sysname is not None: set_system(sysname)
        if baseurl is not None: set_baseurl(baseurl)
        # Authorize with SFAPI
        # USER must export SFAPI_ID and SFAPI_KEY
        # Create a client near the bottom of your IRIS page:
        #   https://iris.nersc.gov/user
        # You will likely have to file a ticket to get permission
        # to do this.
        # Cut and paste the first two values to define these values.
        token_url = "https://oidc.nersc.gov/c2id/token"
        client_id = os.getenv('SFAPI_ID', '')
        if len(client_id) == 0:
            print('>>> The SF API client ID must be stored in SFAPI_ID.')
            exit(1)
        client_key = os.getenv('SFAPI_KEY', '')
        if len(client_key) == 0:
            print('>>> The SF API client ID must be stored in SFAPI_ID.')
            exit(1)
        ldict = {}
        exec(f"val =  {client_key}", globals(), ldict)
        private_key = ldict['val']
        self.session = OAuth2Session(
            client_id, 
            private_key, 
            PrivateKeyJWT(token_url),
            grant_type="client_credentials",
            token_endpoint=token_url
        )
        self.session.fetch_token()

    def message(self, message):
        print(f"Sfapi: {msg}")

    def version(self): return self._version
    def debug(self):   return self._debug
    def timeout(self): return self._timeout
    def sysname(self): return self._sysname
    def baseurl(self): return self._baseurl

    def set_debug(self, dbg):
        self._debug = dbg

    def set_system(self, sysname):
        if sysname in ['perlmutter', 'cori']:
            self._sysname = sysname
        else:
            message(f"ERROR: Ignoring invalid system name: {sysname}")
        return self._sysname

    def set_timeout(self, timeout):
        self._timeout = timeout

    def set_baseurl(self, baseurl):
        self._baseurl = baseurl

    def get_status(self):
        """Return the system status in a string"""
        dbg = self.debug()
        baseurl = self.baseurl()
        if dbg > 1: print('>>> Fetching machine status.')
        url = f"{baseurl}/status/{self.sysname()}"
        r = self.session.get(url)
        jsr = r.json()
        notes = jsr['notes']
        snotes = ''
        if len(notes):
            snotes = f" ({notes[0]}"
            for note in notes[1:]:
                snotes += f", {note}"
            snotes += ')'
        sout = f"{jsr['full_name']}: {jsr['description']}{snotes}, updated {jsr['updated_at']}"
        return sout
    
    def run(self, cmd, showstat=False):
        """
        Run cmd on the system and return stdout.
        Any bash command line appears to work.
        Use redirection to also see stderr (2>&1).
        The return status is recorded in self.return_status.
        """
        dbg = self.debug()
        baseurl = self.baseurl()
        timeout = self.timeout()
        self.return_status = 'fail'
        if dbg: print(f">>> Command: {cmd}")
        url = f"{baseurl}/utilities/command/{self.sysname()}"
        data={"executable": cmd}
        if dbg > 2:
            print(f">>> Post {data} to {url}")
        elif dbg > 1:
            print(f">>> Url: {url}")
            print(f">>> Data: {data}")
        nto = 0
        while True:
            try:
                r = self.session.post(url, data=data, timeout=timeout)
                break
            except requests.exceptions.ReadTimeout:
                if dbg: print(f">>> ... Post timed out ({timeout} sec). ", end='')
                nto == 1
                if nto > 4:
                    print("Giving up.")
                    exit(1)
                print("Trying again.")
        if str(r) == '<Response [500]>':
            print(f">>> It appears that {self.sysname()} is not responding")
            exit(1)
        try:
            jsr = r.json()
        except:
            print(f">>> Unable to decode response from post: {r}")
            exit(0)
        if dbg > 1: print(f">>> Response: {jsr}")
        if 'task_id' not in jsr:
            print('>>> Post to run command failed: {jsr}')
            exit(0)
        task_id = jsr['task_id']
        if dbg > 1: print(f">>> Fetching command response.")
        url = f"{baseurl}/tasks/{task_id}"
        if dbg > 1: print(f">>> Looping on get with url: '{url}'")
        dodot = dbg == 2
        dotpre = '>>> '
        for i in range(20):
            time.sleep(2)
            if dbg > 2: print(f">>> ... Get from {url}")
            if dbg == 2:
                print(f"{dotpre}.", end='', flush=True)
                dotpre = ''
            try:
                sres = None
                r = self.session.get(url, timeout=timeout)
                sres = r.json()['result']
                if dbg > 2: print(f">>> ... Result: {sres}")
            except requests.exceptions.ReadTimeout:
                if dbg > 1:
                    if dodot:
                        dotpre = '>>> '
                    else:
                        print(f">>> ...", end='')
                    print(f" Get timed out ({timeout} sec). Trying again.")
            if sres is not None: break
        if dodot: print('')
        if sres is None:
            print('>>> Timed out fetching result.')
        self.return_status = json.loads(sres)['status']
        if dbg: print(f">>> Command return status: {self.return_status}")
        sout = json.loads(sres)['output']
        self.stdout = sout
        return sout

if __name__ == '__main__':

    args = sys.argv[1:]

    if len(args) < 1 or args[0]=='-h':
        print('Usage: sfapi [-d DBG] [-t TOUT] [-s] [cori] ACT ARGS')
        print('  DBG is the debug level: 0-3, 1 is default')
        print('  TOUT is the timeout for get/post in sec. 10 is default')
        print('  If -s is given, the status (ok, error or fail) is displayed')
        print('  instead of stdout when a command is run.')
        print('  cori to use it instead of perlmutter.')
        print('  ACT ARGS is one of:')
        print('        status: to show machine status.')
        print('    submit FIL: to submit FIL to batch.')
        print('       run COM: run command COM.')
        exit(0)

    sfo = Sfapi()

    if len(args) == 1 and args[0]=='-v':
        print(sfo.version())
        exit(0)

    show_status = False
    while args[0][0] == '-':
        opt = args[0]
        if opt == '-d':
            val = args[1]
            args = args[2:]
            dbg = int(val)
            sfo.set_debug(dbg)
        elif opt == '-t':
            val = args[1]
            args = args[2:]
            tout = int(val)
            sfo.set_timeout(tout)
        elif opt == '-s':
            args = args[1:]
            show_status = True
        else:
            print(f">>> Ignoring invalid option: {opt}")

    # Overrride default system (perlmutter).
    if args[0] == 'cori':
        sfo.set_system('cori')
        args = args[1:]

    # First argument is the action:
    #   status - Show system status
    #   run command - Runs the command on a login node
    #   command - Runs the command on a login node
    #   submit file - Submits file to batch
    act = args[0]
    if act in ['status', 'run', 'submit']:
        args = args[1:]
    else:
        act = 'run'
    
    if act == 'status':
        print(sfo.get_status())

    elif act == 'submit':
        print('>>> Option submit is not yet supported.')

    else:
        cmd = ""
        for arg in args:
            cmd += ' ' + arg
        cmd = cmd.strip()
        sout = sfo.run(cmd)
        if show_status: print(sfo.return_status)
        else: print(sout, end='')
