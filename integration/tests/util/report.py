"""Creates a report for the test.
"""

import atexit
import os
import shutil
import sys
import time
from os import path
from tests.util import test_config


class Reporter(object):
    """Saves the logs from a test run."""

    def __init__(self, root_path):
        self.root_path = root_path
        if not path.exists(self.root_path):
            os.mkdir(self.root_path)
        for file in os.listdir(self.root_path):
            if file.endswith(".log"):
                os.remove(path.join(self.root_path, file))

    def _find_all_instance_ids(self):
        instances = []
        for dir in os.listdir("/vz/private"):
            instances.append(dir)
        return instances

    def log(self, msg):
        with open("%s/report.log" % self.root_path, 'a') as file:
            file.write(str(msg) + "\n")

    def _save_syslog(self):
        try:
            shutil.copyfile("/var/log/syslog", "host-syslog.log")
        except (shutil.Error, IOError) as err:
            self.log("ERROR logging syslog : %s" % (err))

    def _update_instance(self, id):
        root = "%s/%s" % (self.root_path, id)
        try:
            shutil.copyfile("/vz/private/%s/var/log/firstboot" % id,
                            "%s-firstboot.log" % root)
        except (shutil.Error, IOError) as err:
            self.log("ERROR logging firstboot for instance id %s! : %s"
                     % (id, err))
        try:
            shutil.copyfile("/vz/private/%s/var/log/syslog" % id,
                            "%s-syslog.log" % root)
        except (shutil.Error, IOError) as err:
            self.log("ERROR logging firstboot for instance id %s! : %s"
                     % (id, err))

    def _update_instances(self):
        for id in self._find_all_instance_ids():
            self._update_instance(id)

    def update(self):
        self._update_instances()
        self._save_syslog()


REPORTER = Reporter(test_config.values["report_directory"])


def log(msg):
    REPORTER.log(msg)

def update():
    REPORTER.update()
