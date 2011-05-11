# Copyright (c) 2011 OpenStack, LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Functions to initiate and shut down services needed by the tests."""

import os
import subprocess
import time

from httplib2 import Http
from nose.plugins.skip import SkipTest

from proboscis import decorators


def _is_web_service_alive(url):
    """Does a HTTP GET request to see if the web service is up."""
    client = Http()
    try:
        resp = client.request(url, 'GET')
        return resp != None
    except Exception:
        return False


_running_services = []



def get_running_services():
    """ Returns the list of services which this program has started."""
    return _running_services


def start_proc(cmd, shell=False):
    """Given a command, starts and returns a process."""
    env = os.environ.copy()
    proc = subprocess.Popen(
        cmd,
        shell=shell,
        stdin=subprocess.PIPE,
        bufsize=0,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    return proc


class Service(object):
    """Starts and stops a service under test.

    The methods to start and stop the service will not actually do anything
    if they detect the service is already running on this machine.  This is
    because it may be useful for developers to start the services themselves
    some other way.

    """

    # TODO(tim.simpson): Hard to follow, consider renaming certain attributes.

    def __init__(self, cmd):
        """Defines a service to run."""
        if not isinstance(cmd, list):
            raise TypeError()
        self.cmd = cmd
        self.do_not_manage_proc = False
        self.proc = None

    def __del__(self):
        if self.is_running:
            self.stop()

    def ensure_started(self):
        """Starts the service if it is not running."""
        if not self.is_running:
            self.start()

    def find_proc_id(self):
        """Finds and returns the process id."""
        if not self.cmd:
            return False
        proc = start_proc("ps aux", shell=True)
        pid = None
        for line in iter(proc.stdout.readline, ""):
            found = True
            for arg in self.cmd[1:]:
                if line.find(arg) < 0:
                    found = False
                    break
            if found:
                if pid != None:
                    raise RuntimeError("Found PID twice.")
                parts = line.split()
                pid = int(parts[1])
        return pid

    def is_service_alive(self):
        """Searches for the process to see if its alive.

         This function will return true even if this class has not started
         the service (searches using ps).

         """
        if not self.cmd:
            return False
        time.sleep(1)
        proc = start_proc("ps aux", shell=True)
        for line in iter(proc.stdout.readline, ""):
            found = True
            for arg in self.cmd[1:]:
                if line.find(arg) < 0:
                    found = False
                    break
            if found:
                return True
        return False

    @property
    def is_running(self):
        """Returns true if the service has already been started.

        Returns true if this program has started the service or if it
        previously detected it had started.  The main use of this property
        is to know if the service was already begun by this program-
        use is_service_alive for a more definitive answer.

        """
        return self.proc or self.do_not_manage_proc

    def start(self, time_out=3):
        """Starts the service if necessary."""
        if self.is_running:
            raise RuntimeError("Process is already running.")
        if self.is_service_alive():
            self.do_not_manage_proc = True
            return
        self.proc = start_proc(self.cmd, shell=False)
        if not self._wait_for_start(time_out=time_out):
            self.stop()
            raise RuntimeError("Issued the command successfully but the "
                               "service (" + str(self.cmd) +
                               ") never seemed to start.")
        _running_services.append(self)

    def stop(self):
        """Stops the service, but only if this program started it."""
        if self.do_not_manage_proc:
            return
        if not self.proc:
            raise RuntimeError("Process was not started.")
        self.proc.terminate()
        self.proc.kill()
        self.proc.wait()
        self.proc.stdin.close()
        pid = self.find_proc_id()
        if pid:
            start_proc("sudo kill -9 " + str(pid), shell=True)
            time.sleep(1)
        if self.is_service_alive():
            raise RuntimeError('Cannot kill process, PID=' +
                               str(self.proc.pid))
        self.proc = None
        global _running_services
        _running_services = (svc for svc in _running_services if svc != self)

    def _wait_for_start(self, time_out):
        """Waits until time_out (in seconds) for service to appear."""
        give_up_time = time.time() + time_out
        while time.time() < give_up_time:
            if self.is_service_alive():
                return True
        return False


class WebService(Service):
    """Starts and stops a web service under test."""

    def __init__(self, cmd, url):
        """Defines a service to run."""
        Service.__init__(self, cmd)
        if not isinstance(url, (str, unicode)):
            raise TypeError()
        self.url = url
        self.do_not_manage_proc = self.is_service_alive()

    def is_service_alive(self):
        """Searches for the process to see if its alive."""
        return _is_web_service_alive(self.url)
