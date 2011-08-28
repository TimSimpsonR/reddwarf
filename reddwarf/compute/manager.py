# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 Openstack, LLC.
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

import json

from nova import exception
from nova import flags
from nova import log as logging
from nova.api.platform.dbaas import common
from nova.compute import power_state
from nova.guest import api as guest_api
from nova.notifier import api as notifier
from nova import utils

from nova.compute.manager import ComputeManager as NovaComputeManager

from reddwarf.db import api as dbapi

flags.DEFINE_integer('reddwarf_guest_initialize_time_out', 10 * 60,
                     'Time in seconds for a guest to initialize before it is '
                     'considered a failure and aborted.')
flags.DEFINE_integer('reddwarf_instance_suspend_time_out', 3 * 60,
                     'Time in seconds for a compute instance to suspend '
                     'during when aborted before a PollTimeOut is raised.')

FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)
VALID_ABORT_STATES = [
    power_state.CRASHED,
    power_state.FAILED,
    power_state.PAUSED,
    power_state.SUSPENDED,
    power_state.SHUTDOWN
]
#
#AUDIT_ERROR_MESSAGES = {
#    "volume" :  _("Aborting instance %d because the associated volume failed "
#                  "to provision."),
#    "compute" : _("Aborting instance %d because the underlying compute "
#                  "instance failed to run."),
#    "guest" : _("Aborting instance %d because the guest did not initialize.")
#}

def publisher_id(host=None):
    return notifier.publisher_id("reddwarf-compute", host)


class ReddwarfInstanceMetaData(object):
    """Represents standard Reddwarf instance metadata."""

    def __init__(self, context, instance_id):
        """Populates volume, volume_mount_point and databases properties."""
        metadata = self.db.instance_metadata_get(context, instance_id)
        # There shouldn't be exceptions coming from below mean the dbcontainers
        # REST API is misbehaving and sending invalid data.
        # Grabs the volume for this instance with its mount_point, or None.
        self.volume_id = int(metadata['volume_id'])
        self.volume = self.db.volume_get(context, volume_id)
        self.volume_mount_point = metadata.get('mount_point',
                                               "/mnt/" + str(volume_id))
        # Get the databases to create along with this instance.
        databases_list = json.loads(metadata['database_list'])
        self.databases = common.populate_databases(databases_list)


class ComputeManager(NovaComputeManager):
    """Manages the running instances from creation to destruction."""

    def __init__(self, *args, **kwargs):
        super(ComputeManager, self).__init__(*args, **kwargs)
        self.guest_api = guest_api.API()

    def _abort_guest_install(self, context, instance_id):
        """Sets the guest state to FAIL continuously until an instance is known
         to have been suspended, or raises a PollTimeOut exception."""
        self._set_instance_status_to_fail(instance_id)
        LOG.audit(_("Aborting db instance %d.") % instance_id, context=context)
        self.suspend_instance(context, instance_id)

        # Wait for the state has become suspended so we know the guest won't
        # wake up and change its state. All the while until the end, set
        # the state to failed (in reality the suspension should occur quickly
        # and normally we will not be aborting because we didn't wait
        # long enough).

        def get_instance_state():
            return self.db.instance_get(context, instance_id).state

        def confirm_state_is_suspended(instance_state):
            # Make sure the guest state is set to FAILED after suspend, in
            # case it wakes up and tries anything here.
            self._set_instance_status_to_fail(instance_id)
            return instance_state in VALID_ABORT_STATES

        utils.poll_until(get_instance_state,
                         confirm_state_is_suspended,
                         sleep_time=1,
                         time_out=FLAGS.reddwarf_instance_suspend_time_out)

    def ensure_volume_is_ready(self, context, instance_id, volume,
                               mount_point):
        self.wait_until_volume_is_ready(context, volume)
        #TODO(tim.simpson): This may not be able to be the self.host name.
        # Needs to be something that can identify the compute node.
        self.volume_client.initialize(context, volume['id'], self.host)
        self.db.volume_attached(context, volume['id'],
                                instance_id, mount_point)
        self.volume_api.update(context, volume['id'], {})

#    def _find_requested_databases(self, context, instance_id):
#        """Get the databases to create along with this container."""
#        #TODO(tim.simpson) Grab the metadata only once and get the volume info
#        #                  at the same time.
#        metadata = self.db.instance_metadata_get(context, instance_id)
#        # There shouldn't be exceptions coming from below mean the dbcontainers
#        # REST API is misbehaving and sending invalid data.
#        databases_list = json.loads(metadata['database_list'])
#        return common.populate_databases(databases_list)

#    def get_volume_info_for_instance_id(self, context, instance_id):
#        """Returns the volume for this instance with its mount_point, or None.
#
#        We're using this to pass volumes.
#
#        """
#        metadata = self.db.instance_metadata_get(context, instance_id)
#        try:
#            volume_id = int(metadata['volume_id'])
#            return self.db.volume_get(context, volume_id), \
#                   metadata.get('mount_point', "/mnt/" + str(volume_id))
#        except ValueError:
#            raise RuntimeError("The volume_id was in an invalid format.")
#        except (KeyError, exception.VolumeNotFound):
#            return None, None

    def _initialize_compute_instance(self, context, instance_id, **kwargs):
        """Runs underlying compute instance and aborts if any errors occur."""
        try:
            super(ComputeManager, self)._run_instance(context, instance_id,
                                                      **kwargs)
            return True
        except Exception as e:
            self._set_instance_status_to_fail(instance_id)
            self._notify_of_failure(context, instance_id, exception=e,
                event_type='reddwarf.instance.abort.compute',
                audit_msg=_("Aborting instance %d because the underlying "
                            "compute instance failed to run."))
            self.suspend_instance(context, instance_id)
            return False

    def _initialize_guest(self, context, instance_id, databases):
        """Tell the guest to initialize itself and wait for it to happen.

        This method aborts the guest if there's a timeout.

        """
        try:
            self.guest_api.prepare(context, instance_id, databases)
            utils.poll_until(lambda : dbapi.guest_status_get(instance_id),
                             lambda status : status == power_state.RUNNING,
                             sleep_time=2,
                             time_out=FLAGS.reddwarf_guest_initialize_time_out)
            return True
        except utils.PollTimeOut as pto:
            self._set_instance_status_to_fail(instance_id)
            self._notify_of_failure(context, instance_id, exception=pto,
                event_type='reddwarf.instance.abort.guest',
                audit_msg=_("Aborting instance %d because the guest did not "
                            "initialize."))
            self._abort_guest_install(context, instance_id)
            return False

    def _initialize_volume(self, context, instance_id, volume, mount_point):
        try:
            self.ensure_volume_is_ready(context, instance_id, volume,
                                        mount_point)
            return True
        except Exception as e:
            self._set_instance_status_to_fail(instance_id)
            self._notify_of_failure(context, instance_id, exception=e,
                event_type='reddwarf.instance.abort.volume',
                audit_msg=_("Aborting instance %d because the associated "
                            "volume failed to provision."))
            return False

    def _notify_of_failure(self, context, instance_idd,
                         event_type, exception, audit_msg):
        """Logs message / sends notification that an instance has failed."""
        LOG.error(e)
        err_values = { 'instance_id':instance_id, 'volume_id':volume_id }
        LOG.audit(audit_msg % err_values, context=context)
        notifier.notify(publisher_id(), event_type, notifier.ERROR, err_values)

    def _run_instance(self, context, instance_id, **kwargs):
        """Launch a new instance with specified options."""        
        metadata = ReddwarfInstanceMetaData(context, instance_id)
        # If any steps return False, cancel subsequent steps..
        (self._initialize_volume(context, instance_id, metadata.volume,
                                metadata.mount_point) and
         self._initialize_compute_instance(context, instance_id, **kwargs) and
         self._initialize_guest(context, instance_id, metadata.databases))

    def _set_instance_status_to_fail(self, instance_id):
        """Sets the instance to FAIL."""
        dbapi.guest_status_update(instance_id, power_state.FAILED)

    def wait_until_volume_is_ready(self, context, volume):
        """Sleeps until the given volume has finished provisioning."""
        # TODO(tim.simpson): This needs a time out.
        def get_status(volume_id):
            volume = self.db.volume_get(context, volume_id)
            status = volume['status']
            if status == 'creating':
                return
            elif status == 'available':
                raise LoopingCallDone(retvalue=volume)
            elif status != 'available':
                LOG.error("STATUS: %s" % status)
                raise exception.VolumeProvisioningError(volume_id=volume['id'])
        return LoopingCall(get_status, volume['id']).start(3).wait()
