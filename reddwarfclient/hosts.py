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

from novaclient import base


class Host(base.Resource):
    """
    A Hosts is an opaque container used to store Host instances.
    """
    def __repr__(self):
        return "<Host: %s>" % self.name

class Hosts(base.ManagerWithFind):
    """
    Manage :class:`Host` resources.
    """
    resource_class = Host

    def _list(self, url, response_key):
        resp, body = self.api.client.get(url)
        if not body:
            raise Exception("Call to " + url + " did not return a body.")
        return [self.resource_class(self, res) for res in body[response_key]]

    def index(self):
        """
        Get a list of all dbcontainers.

        :rtype: list of :class:`DbContainer`.
        """
        return self._list("/mgmt/hosts", "hosts")

    def get(self, host):
        """
        Get a specific containers.

        :rtype: :class:`DbContainer`
        """
        return self._get("/mgmt/hosts/%s" % self._get_host_name(host), "host")

    def _get_host_name(self, host):
        try:
            if host.name:
                return host.name
        except AttributeError:
            return host
