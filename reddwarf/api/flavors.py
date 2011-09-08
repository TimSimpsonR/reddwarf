# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
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

import webob

from nova import db
from nova import exception
from nova import log as logging
from nova.api.openstack import wsgi
from nova.api.openstack.flavors import Controller as OriginalController
from reddwarf.api import views


LOG = logging.getLogger('reddwarf.api.flavors')
LOG.setLevel(logging.DEBUG)


class ControllerV10(OriginalController):

    def _get_view_builder(self, req):
        LOG.debug("_get_view_builder for flavors")
        return views.flavors.ViewBuilder(base_url=req.application_url)


def create_resource(version='1.0'):
    controller = {
        '1.0': ControllerV10,
    }[version]()

    xmlns = {
        '1.0': wsgi.XMLNS_V10,
    }[version]

    body_serializers = {
        'application/xml': wsgi.XMLDictSerializer(xmlns=xmlns),
    }

    serializer = wsgi.ResponseSerializer(body_serializers)

    return wsgi.Resource(controller, serializer=serializer)
