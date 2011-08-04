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

import unittest
import os
import time
import socket

from nose.plugins.skip import SkipTest
from nova import context
from nova import utils
from nova.db import api as dbapi

from proboscis import test
from proboscis.decorators import time_out
from tests.util import test_config
from tests.util.services import Service
from tests.util.services import start_proc
from tests.util.services import WebService
from tests.util.test_config import glance_bin_root
from tests.util.test_config import glance_images_directory
from tests.util.test_config import nova_code_root
from tests.util.test_config import python_cmd_list

dbaas_image = None
container_name = None
success_statuses = ["build", "active"]


def dbaas_url():
    return str(test_config.values.get("dbaas_url"))

def glance_api_conf():
    return str(test_config.values.get("glance_api_conf"))

def glance_reg_conf():
    return str(test_config.values.get("glance_reg_conf"))

def nova_conf():
    return str(test_config.values.get("nova_conf"))

def nova_url():
    return str(test_config.values.get("nova_url"))

def either_web_service_is_up():
    return test_config.dbaas.is_service_alive() or \
           test_config.nova.is_service_alive()

install_image = False

@test(groups=["services.initialize", "services.initialize.glance"])
class GlanceRegistry(unittest.TestCase):
    """Starts the glance registry."""

    def setUp(self):
        if os.path.exists("%sglance-registry" % glance_bin_root()):
            reg_path = "%sglance-registry" % glance_bin_root()
        else:
            reg_path = "/usr/bin/glance-registry"
        self.service = Service(python_cmd_list() +
                               [reg_path, glance_reg_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()

@test(groups=["services.initialize", "services.initialize.glance"],
      depends_on_classes=[GlanceRegistry])
class GlanceApi(unittest.TestCase):
    """Starts the glance registry."""

    def setUp(self):
        if os.path.exists("%sglance-api" % glance_bin_root()):
            reg_path = "%sglance-api" % glance_bin_root()
        else:
            reg_path = "/usr/bin/glance-api"
        self.service = Service(python_cmd_list() +
                               [reg_path, glance_api_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()

@test(groups=["services.initialize", "services.initialize.glance"],
      depends_on_classes=[GlanceApi])
class AddGlanceImage(unittest.TestCase):
    """Starts the glance registry."""

    def test_start(self):
        if os.environ.get("INSTALL_GLANCE_IMAGE", "False") == 'True':
            # Check if glance-upload is package installed or not by
            # just checking if the 'known' glance-upload exists
            if os.path.exists("%sglance-upload" % glance_bin_root()):
                exec_str = "%sglance-upload" % glance_bin_root()
            else:
                exec_str = "/usr/bin/glance-upload"
            proc = start_proc([exec_str, "--type=raw",
                               "%s/ubuntu-10.04-x86_64-openvz.tar.gz" %
                               glance_images_directory(),
                               "ubuntu-10.04-x86_64-openvz"])
            (stdoutdata, stderrdata) = proc.communicate()
            print "proc.communicate()'s stdout\n%s" % stdoutdata
            print "proc.communicate()'s stderr\n%s" % stderrdata


@test(groups=["services.initialize"], depends_on_classes=[GlanceApi])
class Network(unittest.TestCase):
    """Starts the network service."""

    def setUp(self):
        self.service = Service(python_cmd_list() +
                               ["%s/bin/nova-network" % nova_code_root(),
                                "--flagfile=%s" % nova_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()


@test(groups=["services.initialize"], depends_on_classes=[GlanceApi])
class Dns(unittest.TestCase):
    """Starts the network service."""

    def setUp(self):
        self.service = Service(python_cmd_list() +
                               ["%s/bin/nova-dns" % nova_code_root(),
                                "--flagfile=%s" % nova_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()


@test(groups=["services.initialize"])
class Scheduler(unittest.TestCase):
    """Starts the scheduler service."""

    def setUp(self):
        self.service = Service(python_cmd_list() +
                               ["%s/bin/nova-scheduler" % nova_code_root(),
                                "--flagfile=%s" % nova_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()


@test(groups=["services.initialize"], depends_on_classes=[GlanceApi, Network])
class Compute(unittest.TestCase):
    """Starts the compute service."""

    def setUp(self):
        self.service = Service(python_cmd_list() +
                               ["%s/bin/nova-compute" % nova_code_root(),
                                "--flagfile=%s" % nova_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()


@test(groups=["services.initialize"], depends_on_classes=[Scheduler])
class Volume(unittest.TestCase):
    """Starts the volume service."""

    def setUp(self):
        self.service = Service(python_cmd_list() +
                               ["%s/bin/nova-volume" % nova_code_root(),
                                "--flagfile=%s" % nova_conf() ])

    def test_start(self):
        if not either_web_service_is_up():
            self.service.start()


@test(groups=["services.initialize"],
      depends_on_classes=[Compute, Network, Scheduler, Volume])
class Api(unittest.TestCase):
    """Starts the compute service."""

    def setUp(self):
        self.service = test_config.nova

    def test_start(self):
        if not self.service.is_service_alive():
            self.service.start(time_out=60)


@test(groups=["services.initialize"],
      depends_on_classes=[Compute, Network, Scheduler, Volume])
class PlatformApi(unittest.TestCase):
    """Starts the compute service."""

    def setUp(self):
        self.service = test_config.dbaas

    def test_start(self):
        if not self.service.is_service_alive():
            self.service.start(time_out=60)


@test(groups=["services.initialize"],
      depends_on_classes=[Compute, Network, Scheduler, Volume])
class WaitForTopics(unittest.TestCase):
    """Waits until needed services are up."""

    @time_out(60)
    def test_start(self):
        topics = ["compute", "volume"]
        from tests.util.topics import hosts_up
        while not all(hosts_up(topic) for topic in topics):
            pass


@test(groups=["services.initialize"],
      depends_on_classes=[WaitForTopics])
class ServicesTestable(unittest.TestCase):
    """Check Services are ready for Tests

    Use this class to add extra checks for services to be completely up,
    no exceptions... 100% ready to go
    """

    @time_out(60 * 3)
    def test_networks_have_host_assigned(self):
        """
        ServicesUp - Check that default networks have a host assigned
        """
        while(True):
            networks = dbapi.network_get_all_by_host(context.get_admin_context(),
                                                     socket.gethostname())
            if len(networks) == 2:
                return
            time.sleep(5)


@test(groups=["start_and_wait"],
      depends_on_groups=["services.initialize"],
      enabled=(os.environ.get("SERVICE_WAIT", 'False') == 'True'))
class StartAndWait(unittest.TestCase):

    def test(self):
        import time
        while(True):
            time.sleep(2)

