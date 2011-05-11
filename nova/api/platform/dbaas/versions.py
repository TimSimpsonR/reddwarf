# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

import webob.dec
import webob.exc

from nova import wsgi
import nova.api.openstack.views.versions


class Versions(wsgi.Application):
    """Supported versions"""

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req, start_response):
        """Respond to a request for all DBaaS API versions."""
        version_objs = [
            {
                "id": "v1.0",
                "status": "CURRENT",
            }
        ]

        builder = nova.api.openstack.views.versions.get_view_builder(req)
        versions = [builder.build(version) for version in version_objs]
        response = dict(versions=versions)

        metadata = {
            "application/xml": {
                "attributes": {
                    "version": ["status", "id"],
                    "link": ["rel", "href"],
                }
            }
        }

        content_type = req.best_match_content_type()
        return wsgi.Serializer(metadata).serialize(response, content_type)
