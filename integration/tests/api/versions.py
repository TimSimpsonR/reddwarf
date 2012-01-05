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

from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_equal

import tests
from tests.util import test_config
from tests.util import create_dbaas_client
from tests.util.users import Requirements

GROUP="dbaas.api.versions"


@test(groups=[tests.DBAAS_API, GROUP, tests.PRE_INSTANCES, 'DBAAS_VERSIONS'],
      depends_on_groups=["services.initialize"])
class Versions(object):
    """Test listing all versions and verify the current version"""

    @before_class
    def setUp(self):
        """Sets up the client."""
        user = test_config.users.find_user(Requirements(is_admin=False))
        self.client = create_dbaas_client(user)

    @test
    def test_list_versions_index(self):
        versions = self.client.versions.index(test_config.version_url)
        assert_equal(1, len(versions))
        assert_equal("CURRENT", versions[0].status,
                     message="Version status: %s" % versions[0].status)
        assert_equal("v1.0", versions[0].id,
                     message="Version ID: %s" % versions[0].id)

    def _request(self, url, method='GET', response='200'):
        resp, body = None, None
        try:
            resp, body = self.client.client.request('http://localhost:8775' + url, method)
            assert_equal(resp.get('status', ''), response)
        except Exception:
            pass
        return body

    @test
    def test_no_slash_no_version(self):
        body = self._request('')

    @test
    def test_no_slash_with_version(self):
        body = self._request('/v1.0')

    @test
    def test_with_slash_no_version(self):
        body = self._request('/')

    @test
    def test_with_slash_with_version(self):
        body = self._request('/v1.0/')

    @test
    def test_request_no_version(self):
        body = self._request('/dbaas/instances', response='404')

    @test
    def test_request_bogus_version(self):
        body = self._request('/0.0/', response='404')
