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

import time

from sqlalchemy.sql.expression import text
from sqlalchemy import exc

from reddwarf.guest.dbaas import LocalSqlClient

from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_not_equal
from proboscis.asserts import assert_raises
from proboscis.asserts import assert_true
from proboscis.asserts import fail
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out

import tests
from tests.api.users import TestUsers
from tests.api.instances import instance_info
from tests.util import init_engine
from tests import util

GROUP="dbaas.api.root"


@test(depends_on_classes=[TestUsers], groups=[tests.DBAAS_API, GROUP,
                                                  tests.INSTANCES])
class TestRoot(object):
    """
    Test the root operations
    """

    root_enabled_timestamp = 'Never'
    system_users = ['root', 'debian_sys_maint']

    @before_class
    def setUp(self):
        self.dbaas = util.create_dbaas_client(instance_info.user)
        self.dbaas_admin = util.create_dbaas_client(instance_info.admin_user)

    def _verify_root_timestamp(self, id):
        mgmt_instance = self.dbaas_admin.management.show(id)
        assert_true(mgmt_instance is not None)
        timestamp = mgmt_instance.root_enabled_at
        assert_equal(self.root_enabled_timestamp, timestamp)
        reh = self.dbaas_admin.management.root_enabled_history(id)
        print "Root_enabled_history is %s" % reh
        timestamp = reh.root_enabled_at
        assert_equal(self.root_enabled_timestamp, timestamp)
        assert_equal(id, reh.id)

    def _root(self):
        global root_password
        global root_user
        host = "%"
        user, password = self.dbaas.root.create(instance_info.id)

        engine = init_engine(user, password, instance_info.user_ip)
        client = LocalSqlClient(engine)
        with client:
            t = text("""SELECT User, Host FROM mysql.user WHERE User=:user AND Host=:host;""")
            result = client.execute(t, user=user, host=host)
            for row in result:
                assert_equal(user, row['User'])
                assert_equal(host, row['Host'])
        root_password = password
        root_user = user
        self.root_enabled_timestamp = self.dbaas_admin.management.show(instance_info.id).root_enabled_at
        assert_not_equal(self.root_enabled_timestamp, 'Never')

    @test
    def test_root_initially_disabled(self):
        """Test that root is disabled"""
        enabled = self.dbaas.root.is_root_enabled(instance_info.id)
        assert_false(enabled, "Root SHOULD NOT be enabled.")

    @test(depends_on=[test_root_initially_disabled])
    def test_root_initially_disabled_details(self):
        """Use instance details to test that root is disabled."""
        instance = self.dbaas.instances.get(instance_info.id)
        assert_true(hasattr(instance, 'rootEnabled'),
                    "Instance has no rootEnabled property.")
        assert_false(instance.rootEnabled, "Root SHOULD NOT be enabled.")
        assert_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)

    @test(depends_on=[test_root_initially_disabled_details])
    def test_enable_root(self):
        self._root()
        assert_not_equal(self.root_enabled_timestamp, 'Never')

    @test(depends_on=[test_enable_root])
    def test_verify_root_load_file(self):
        global root_user
        global root_password
        engine = init_engine(root_user, root_password, instance_info.user_ip)
        client = LocalSqlClient(engine)
        with client:
            t = text("""SELECT load_file("/etc/nova/guest.conf");""")
            result = client.execute(t)
            print result
            for row in result:
                print row
                assert_equal(None, row[0])

    @test(depends_on=[test_enable_root])
    def test_verify_root_cannot_create_super_user(self):
        """
        Next check that root is not able to create a new user with full perms.
        """
        global root_user
        global root_password
        super_user = "foo"
        super_pwd = "foo"
        host = "%"
        engine = init_engine(root_user, root_password, instance_info.user_ip)
        client = LocalSqlClient(engine)
        with client:
            t = text("""CREATE USER :user@:host;""")
            client.execute(t, user=super_user, host=host)
            t = text("""UPDATE mysql.user SET Password=PASSWORD(:pwd)
                        WHERE User=:user;""")
            client.execute(t, pwd=super_pwd, user=super_user)
            t = text("""GRANT ALL PRIVILEGES ON *.* TO :user@:host
                        WITH GRANT OPTION;""")
            assert_raises(exc.OperationalError,
                          client.execute, t, user=super_user, host=host)
            t = text("""DROP USER :user@:host""")
            client.execute(t, user=super_user, host=host)

    @test(depends_on=[test_enable_root])
    def test_root_now_enabled(self):
        """Test that root is now enabled."""
        enabled = self.dbaas.root.is_root_enabled(instance_info.id)
        assert_true(enabled, "Root SHOULD be enabled.")

    @test(depends_on=[test_root_now_enabled])
    def test_root_now_enabled_details(self):
        """Use instance details to test that root is now enabled."""
        instance = self.dbaas.instances.get(instance_info.id)
        assert_true(hasattr(instance, 'rootEnabled'),
                    "Instance has no rootEnabled property.")
        assert_true(instance.rootEnabled, "Root SHOULD be enabled.")
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)

    @test(depends_on=[test_root_now_enabled_details])
    def test_reset_root(self):
        old_ts = self.root_enabled_timestamp
        self._root()
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        assert_equal(self.root_enabled_timestamp, old_ts)

    @test(depends_on=[test_reset_root])
    def test_root_still_enabled(self):
        """Test that after root was reset it's still enabled."""
        enabled = self.dbaas.root.is_root_enabled(instance_info.id)
        assert_true(enabled, "Root SHOULD still be enabled.")

    @test(depends_on=[test_root_still_enabled])
    def test_root_still_enabled_details(self):
        """Use instance details to test that after root was reset it's still enabled."""
        instance = self.dbaas.instances.get(instance_info.id)
        assert_true(hasattr(instance, 'rootEnabled'),
                    "Instance has no rootEnabled property.")
        assert_true(instance.rootEnabled, "Root SHOULD still be enabled.")
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)

    @test(depends_on=[test_root_still_enabled_details])
    def test_reset_root_user_enabled(self):
        created_users= ['root']
        self.system_users.remove('root')
        users = self.dbaas.users.list(instance_info.id)
        found = False
        for user in created_users:
            found = any(result.name == user for result in users)
            assert_true(found, "User '%s' not found in result" % user)
            found = False

        found = False
        for user in self.system_users:
            found = any(result.name == user for result in users)
            assert_false(found, "User '%s' SHOULD NOT BE found in result" % user)
            found = False
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)
