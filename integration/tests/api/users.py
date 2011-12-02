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
import re

from novaclient import exceptions as nova_exceptions

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
from tests.api.databases import TestDatabases
from tests.api.instances import instance_info
from tests.util import process
from tests import util

GROUP="dbaas.api.users"


@test(depends_on_classes=[TestDatabases], groups=[tests.DBAAS_API, GROUP,
                                                  tests.INSTANCES])
class TestUsers(object):
    """
    Test the creation and deletion of users
    """

    username = "tes!@#tuser"
    username_urlencoded = "tes%21%40%23tuser"
    password = "testpa$^%ssword"
    username1 = "anous*&^er"
    username1_urlendcoded = "anous%2A%26%5Eer"
    password1 = "anopas*?.sword"
    db1 = "firstdb"
    db2 = "seconddb"

    created_users = [username, username1]
    system_users = ['root', 'debian_sys_maint']

    @before_class
    def setUp(self):
        self.dbaas = util.create_dbaas_client(instance_info.user)
        self.dbaas_admin = util.create_dbaas_client(instance_info.admin_user)

    @test()
    def test_create_users(self):
        users = list()
        users.append({"name": self.username, "password": self.password,
                      "database": self.db1})
        users.append({"name": self.username1, "password": self.password1,
                     "databases": [{"name": self.db1}, {"name": self.db2}]})
        self.dbaas.users.create(instance_info.id, users)
        time.sleep(5)

        self.check_database_for_user(self.username, self.password,
                                    [self.db1])
        self.check_database_for_user(self.username1, self.password1,
                                    [self.db1, self.db2])

    @test(depends_on=[test_create_users])
    def test_create_users_list(self):
        #tests for users that should be listed
        users = self.dbaas.users.list(instance_info.id)
        found = False
        for user in self.created_users:
            for result in users:
                if user == result.name:
                    found = True
            assert_true(found, "User '%s' not found in result" % user)
            found = False

    @test(depends_on=[test_create_users_list])
    def test_create_users_list_system(self):
        #tests for users that should not be listed
        users = self.dbaas.users.list(instance_info.id)
        found = False
        for user in self.system_users:
            found = any(result.name == user for result in users)
            assert_false(found, "User '%s' SHOULD NOT BE found in result" % user)
            found = False

    @test(depends_on=[test_create_users_list])
    def test_delete_users(self):
        self.dbaas.users.delete(instance_info.id, self.username_urlencoded)
        self.dbaas.users.delete(instance_info.id, self.username1_urlendcoded)
        time.sleep(5)

        self._check_connection(self.username, self.password)
        self._check_connection(self.username1, self.password1)

    def check_database_for_user(self, user, password, dbs):
        cmd = "sudo mysql    -h %s -u '%s' -p'%s' -e 'show databases;'" \
              % (instance_info.user_ip, user, password)
        print("Running cmd: %s" % cmd)
        dblist, err = process(cmd)
        print("returned: %s" % dblist)
        if err:
            assert_false(True, err)
        for db in dbs:
            default_db = re.compile("[\w\n]*%s[\w\n]*" % db)
            if not default_db.match(dblist):
                fail("No match for db %s in dblist. %s :(" % (db, dblist))

    @test
    def test_username_too_long(self):
        users = []
        users.append({"name": "1233asdwer345tyg56", "password": self.password,
                      "database": self.db1})
        assert_raises(nova_exceptions.BadRequest, self.dbaas.users.create,
                      instance_info.id, users)

    @test
    def test_invalid_username(self):
        users = []
        users.append({"name": "user,", "password": self.password,
                      "database": self.db1})
        assert_raises(nova_exceptions.BadRequest, self.dbaas.users.create,
                      instance_info.id, users)

    @test
    def test_invalid_password(self):
        users = []
        users.append({"name": "anouser", "password": "sdf,;",
                      "database": self.db1})
        assert_raises(nova_exceptions.BadRequest, self.dbaas.users.create,
                      instance_info.id, users)

    def _check_connection(self, username, password):
        pos_error = re.compile("ERROR 1130 \(HY000\): Host '[\w\.]*' is not allowed to connect to this MySQL server")
        dblist, err = process("sudo mysql -h %s -u '%s' -p'%s' -e 'show databases;'"
                                % (instance_info.user_ip, username, password))
        if not pos_error.match(err):
            fail(err)
