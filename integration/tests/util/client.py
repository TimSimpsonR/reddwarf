# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

"""
:mod:`tests` -- Utility methods for tests.
===================================

.. automodule:: utils
   :platform: Unix
   :synopsis: Tests for Nova.
.. moduleauthor:: Nirmal Ranganathan <nirmal.ranganathan@rackspace.com>
.. moduleauthor:: Tim Simpson <tim.simpson@rackspace.com>
"""


from nose.tools import assert_false
from nose.tools import assert_true

class TestClient(object):
    """Decorates the rich clients with some extra methods.

    These methods are filled with test asserts, meaning if you use this you
    get the tests for free.

    """

    def __init__(self, dbaas_client, os_client=None):
        """Accepts a dbaas and os client. They may have different urls."""
        os_client = os_client or dbaas_client
        self.dbaas_client = dbaas_client
        self.os_client = os_client

    @staticmethod
    def find_flavor_self_href(flavor):
        self_links = [link for link in flavor.links if link['rel'] == 'self']
        assert_true(len(self_links) > 0, "Flavor had no self href!")
        flavor_href = self_links[0]['href']
        assert_false(flavor_href is None, "Flavor link self href missing.")
        return flavor_href

    def find_flavors_by_ram(self, ram):
        assert_false(ram is None)
        flavors = self.flavors.list()
        return [flavor for flavor in flavors if flavor.ram == ram]

    def find_flavor_and_self_href(self, flavor_id):
        """Given an ID, returns flavor and its self href."""
        assert_false(flavor_id is None)
        flavor = self.flavors.get(flavor_id)
        assert_false(flavor is None)
        flavor_href = self.find_flavor_self_href(flavor)
        return flavor, flavor_href

    def find_image_and_self_href(self, image_id):
        """Given an ID, returns tuple with image and its self href."""
        assert_false(image_id is None)
        image = self.images.get(image_id)
        assert_true(image is not None)
        self_links = [link['href'] for link in image.links
                      if link['rel'] == 'self']
        assert_true(len(self_links) > 0,
                        "Found image with ID %s but it had no self link!" %
                        str(image_id))
        image_href = self_links[0]
        assert_false(image_href is None, "Image link self href missing.")
        return image, image_href

    def __getattr__(self, item):
        if item in ['ipgroups', 'servers', 'zones', 'accounts']:
            preferred_client = self.os_client
        else:
            preferred_client = self.dbaas_client
        return getattr(preferred_client, item)
