#    Copyright 2011 OpenStack LLC
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

from novaclient import exceptions

from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_not_equal
from proboscis.asserts import assert_raises
from proboscis.asserts import assert_true
from proboscis.asserts import fail

import tests
from tests.api.instances import create_new_instance
from tests.api.instances import instance_info
from tests.util import test_config
from tests.util import create_dbaas_client
from tests.util.users import Requirements

GROUP="dbaas.api.mgmt.hosts"


@test(groups=[tests.DBAAS_API, GROUP, tests.PRE_INSTANCES],
      depends_on_groups=["services.initialize"])
class HostsBeforeInstanceCreation(object):

    @before_class(enabled=create_new_instance())
    def setUp(self):
        self.user = test_config.users.find_user(Requirements(is_admin=True))
        self.client = create_dbaas_client(self.user)
        self.host = None

    @test(enabled=create_new_instance())
    def test_empty_index_host_list(self):
        host_index_result = self.client.hosts.index()
        assert_not_equal(host_index_result, None,
                         "list hosts call should not be empty: %s" %
                         str(host_index_result))
        assert_equal(len(host_index_result), 1,
                    "list hosts length should be one: %r" %
                    host_index_result[0])
        assert_equal(int(host_index_result[0].instanceCount), 0,
                     "'host' instance count should have 0 running instances: %r"
                     % host_index_result[0].instanceCount)
        for host in list(enumerate(host_index_result, start=1)):
            print("%r host: %r" % (host[0], host[1]))
            self.host = host[1]

    @test(enabled=create_new_instance())
    def test_empty_index_host_list_single(self):
        single_host = self.client.hosts.get(self.host)
        assert_not_equal(single_host, None,
                         "Get host should not be empty for: %s" % self.host)
        print("test_index_host_list_single result: %r" % single_host.__dict__)
        assert_true(single_host.percentUsed == 0,
                    "percentUsed should be 0 : %r" % single_host.percentUsed)
        assert_true(single_host.totalRAM,
                    "totalRAM should exist > 0 : %r" % single_host.totalRAM)
        assert_true(single_host.usedRAM == 0,
                    "usedRAM should be 0 : %r" % single_host.usedRAM)
        assert_true(instance_info.name
                        not in [dbc.name for dbc
                                in single_host.instances])
        instance_info.host_info = single_host
        for index, instance in enumerate(single_host.instances, start=1):
            print("%r instance: %r" % (index, instance))

    @test(enabled=create_new_instance())
    def test_host_not_found(self):
        assert_raises(exceptions.NotFound, self.client.hosts.get, "host@$%3dne")


@test(groups=[tests.INSTANCES, GROUP], depends_on_groups=["dbaas.listing"],
      enabled=create_new_instance())
class HostsAfterInstanceCreation(object):

    @before_class(enabled=create_new_instance())
    def setUp(self):
        self.user = test_config.users.find_user(Requirements(is_admin=True))
        self.client = create_dbaas_client(self.user)
        self.host = None

    @test(enabled=create_new_instance())
    def test_index_host_list(self):
        myresult = self.client.hosts.index()
        assert_true(len(myresult) > 0,
                        "list hosts should not be empty: %s" % str(myresult))
        assert_equal(myresult[0].instanceCount, 1,
                     "instance count of 'host' should have 1 running instances: %r"
                     % myresult[0].instanceCount)
        for index, host in enumerate(myresult, start=1):
            print("%d host: %s" % (index, host))
            self.host = host

    @test(enabled=create_new_instance())
    def test_index_host_list_single(self):
        myresult = self.client.hosts.get(self.host)
        assert_not_equal(myresult, None,
                         "list hosts should not be empty: %s" % str(myresult))
        assert_true(len(myresult.instances) > 0,
                    "instance list on the host should not be empty: %r" %
                    myresult.instances)
        assert_true(myresult.totalRAM == instance_info.host_info.totalRAM,
                        "totalRAM should be the same as before : %r == %r" %
                        (myresult.totalRAM, instance_info.host_info.totalRAM))
        diff = instance_info.host_info.usedRAM + instance_info.dbaas_flavor.ram
        assert_true(myresult.usedRAM == diff,
                        "usedRAM should be : %r == %r" %
                        (myresult.usedRAM, diff))
        calc = round(1.0 * myresult.usedRAM / myresult.totalRAM * 100)
        assert_true(myresult.percentUsed == calc,
                        "percentUsed should be : %r == %r" %
                        (myresult.percentUsed, calc))
        print("test_index_host_list_single result instances: %s" %
              str(myresult.instances))
        for index, instance in enumerate(myresult.instances, start=1):
            print("%d instance: %s" % (index, instance))
            assert_equal(['id', 'name', 'status'], sorted(instance.keys()))
