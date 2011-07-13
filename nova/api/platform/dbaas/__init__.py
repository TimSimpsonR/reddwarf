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
WSGI middleware for DBaaS API controllers.
"""

import routes

from nova import flags
from nova import log as logging
from nova import wsgi
from nova.api.openstack import flavors
from nova.api.openstack import images
from nova.api.platform.dbaas import databases
from nova.api.platform.dbaas import dbcontainers
from nova.api.platform.dbaas import guests
from nova.api.platform.dbaas import root
from nova.api.platform.dbaas import users

LOG = logging.getLogger('nova.api.platform.dbaas')
FLAGS = flags.FLAGS

flags.DEFINE_integer('default_guest_mysql_port', 3306,
                     'Default port used for guest mysql instance')
flags.DEFINE_string('default_firewall_rule_name',
                    'tcp_%s' %  FLAGS.default_guest_mysql_port,
                    'Default firewall rule name used for guest instances')
flags.DEFINE_string('nova_api_version', '1.1',
                    'The default nova api version for reddwarf')


class APIRouter(wsgi.Router):
    """
    Routes requests on the DBaaS API to the appropriate controller
    and method.
    """

    @classmethod
    def factory(cls, global_config, **local_config):
        """Simple paste factory, :class:`nova.wsgi.Router` doesn't have one"""
        return cls()

    def __init__(self):
        mapper = routes.Mapper()

        container_members = {'action': 'POST'}
        if FLAGS.allow_admin_api:
            LOG.debug(_("Including admin operations in API."))
            mapper.resource("guest", "guests",
                            controller=guests.create_resource(),
                            collection={'upgradeall': 'POST'},
                            member={'upgrade': 'POST'})

            mapper.resource("image", "images",
                            controller=images.create_resource(FLAGS.nova_api_version),
                            collection={'detail': 'GET'})

            #TODO(rnirmal): Right now any user can access these
            # functions as long as the allow_admin_api flag is set.
            # Need to put something in place so that only real admin
            # users can hit that api, others would just be rejected.

        mapper.resource("dbcontainer", "dbcontainers",
                        controller=dbcontainers.create_resource(),
                        collection={'detail': 'GET'},
                        member=container_members)

        mapper.resource("flavor", "flavors",
                        controller=flavors.create_resource(FLAGS.nova_api_version),
                        collection={'detail': 'GET'})

        mapper.resource("database", "databases",
                        controller=databases.create_resource(),
                        parent_resource=dict(member_name='dbcontainer',
                        collection_name='dbcontainers'))

        mapper.resource("user", "users",
                        controller=users.create_resource(),
                        parent_resource=dict(member_name='dbcontainer',
                        collection_name='dbcontainers'))

        # Using connect instead of resource due to the incompatibility
        # for delete without providing an id.
        mapper.connect("/dbcontainers/{dbcontainer_id}/root",
                       controller=root.create_resource(),
                       action="create", conditions=dict(method=["POST"]))
        mapper.connect("/dbcontainers/{dbcontainer_id}/root",
                       controller=root.create_resource(),
                       action="delete", conditions=dict(method=["DELETE"]))
        mapper.connect("/dbcontainers/{dbcontainer_id}/root",
                       controller=root.create_resource(),
                       action="is_root_enabled", conditions=dict(method=["GET"]))

        super(APIRouter, self).__init__(mapper)
