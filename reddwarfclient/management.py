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
from reddwarfclient.instances import Instance

class Management(base.ManagerWithFind):
    """
    Manage :class:`Instances` resources.
    """
    resource_class = Instance

    def _list(self, url, response_key):
        resp, body = self.api.client.get(url)
        if not body:
            raise Exception("Call to " + url + " did not return a body.")
        return self.resource_class(self, body[response_key])

    def show(self, instance):
        """
        Get details of one instance.

        :rtype: :class:`Instance`.
        """
        
        return self._list("/mgmt/instances/%s" % base.getid(instance),
            'instance')
