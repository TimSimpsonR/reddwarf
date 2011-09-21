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

import time
import urlparse

try:
    import json
except ImportError:
    import simplejson as json


from novaclient.client import HTTPClient
from novaclient.v1_1.client import Client


from reddwarfclient.accounts import Accounts
from reddwarfclient.databases import Databases
from reddwarfclient.instances import Instances
from reddwarfclient.hosts import Hosts
from reddwarfclient.management import Management
from reddwarfclient.root import Root
from reddwarfclient.storage import StorageInfo
from reddwarfclient.users import Users
from reddwarfclient.versions import Versions

# To write this test from an end user perspective, we have to create a client
# similar to the CloudServers one.
# For now we will work on it here.


class ReddwarfHTTPClient(HTTPClient):
    """
    Class for overriding the HTTP authenticate call and making it specific to
    reddwarf
    """

    def __init__(self, user, apikey, tenant, auth_url, service_name,
                 service_url=None, timeout=None):
        super(ReddwarfHTTPClient, self).__init__(user, apikey, tenant,
                                                 auth_url, timeout=timeout)
        self.tenant = tenant
        self.service = service_name
        self.management_url = service_url

    def authenticate(self):
        scheme, netloc, path, query, frag = urlparse.urlsplit(self.auth_url)
        path_parts = path.split('/')
        for part in path_parts:
            if len(part) > 0 and part[0] == 'v':
                self.version = part
                break

        # Auth against Keystone version 2.0
        if self.version == "v2.0":
            req_body = {'passwordCredentials': {'username': self.user,
                                                'password': self.apikey,
                                                'tenantId': self.tenant}}
            self._get_token("/v2.0/tokens", req_body)
        # Auth against Keystone version 1.1
        elif self.version == "v1.1":
            req_body = {'credentials': {'username': self.user,
                                        'key': self.apikey}}
            self._get_token("/v1.1/auth", req_body)
        else:
            raise NotImplementedError("Version %s is not supported"
                                      % self.version)

    def _get_token(self, path, req_body):
        """Set the management url and auth token"""
        token_url = urlparse.urljoin(self.auth_url, path)
        resp, body = self.request(token_url, "POST", body=req_body)
        try:
            if not self.management_url:
                self.management_url = body['auth']['serviceCatalog'] \
                                      [self.service][0]['publicURL']
            self.auth_token = body['auth']['token']['id']
        except KeyError:
            raise NotImplementedError("Service: %s is not available"
                                      % self.service)


class Dbaas(Client):
    """
    Top-level object to access the Rackspace Database as a Service API.

    Create an instance with your creds::

        >>> red = Dbaas(USERNAME, API_KEY, TENANT, AUTH_URL, SERVICE_NAME,
                        SERVICE_URL)

    Then call methods on its managers::

        >>> red.instances.list()
        ...
        >>> red.flavors.list()
        ...

    &c.
    """

    def __init__(self, username, apikey, tenant=None, auth_url=None,
                 service_name='reddwarf', service_url=None):
        super(Dbaas, self).__init__(self, username, apikey, tenant, auth_url)
        self.client = ReddwarfHTTPClient(username, apikey, tenant, auth_url,
                                         service_name, service_url)
        self.versions = Versions(self)
        self.databases = Databases(self)
        self.instances = Instances(self)
        self.users = Users(self)
        self.root = Root(self)
        self.hosts = Hosts(self)
        self.storage = StorageInfo(self)
        self.management = Management(self)
        self.accounts = Accounts(self)
