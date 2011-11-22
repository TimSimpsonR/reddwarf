# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Tests the agents ability to withstand connection loss.

This test takes down rabbit and brings it back up while running the guest and
not restarting it. It tests that the Guest handle Rabbit going down and coming
back up.

"""

import re
import string
import time

from os import path

from proboscis import after_class
from proboscis import before_class
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_true
from proboscis.asserts import fail
from proboscis.decorators import time_out
from proboscis.decorators import TimeoutError
from proboscis import test

from nova import context
from nova import rpc
from nova import utils
from nova.exception import ProcessExecutionError
from tests import util as test_utils
from tests.util import test_config
from tests.util.services import Service
from tests.util.services import start_proc


class Rabbit(object):

    def get_queue_items(self):
        """Returns a count of the queued messages the host has sent."""
        proc = start_proc(["/usr/bin/sudo", "rabbitmqctl", "list_queues"],
                          shell=False)
        for line in iter(proc.stdout.readline, ""):
            print("LIST QUEUES:" + line)
            m = re.search("""guest.host\s+([0-9]+)""", line)
            if m:
                return int(m.group(1))
        return None

    @property
    def is_alive(self):
        """Calls list_queues, should fail."""
        try:
            self.run(0, "rabbitmqctl", "list_queues")
            return True
        except ProcessExecutionError:
            return False

    def reset(self):
        self.run(0, "rabbitmqctl", "reset")

    def run(self, check_exit_code, *cmd):
        return utils.execute(*cmd, run_as_root=True)

    def start(self):
        self.run(0, "rabbitmqctl", "start_app")

    def stop(self):
        self.run(0, "rabbitmqctl", "stop_app")


@test(groups=["agent", "amqp.restarts"])
class WhenAgentRunsAsRabbitGoesUpAndDown(object):
    """Tests the agent is ok when Rabbit 
    """

    def __init__(self):
        self.rabbit = Rabbit()
        self.send_after_reconnect_errors = 0
        self.tolerated_send_errors = 0

    @after_class
    def stop_agent(self):
        self.agent.stop()

    def _send(self):
        original_queue_count = self.rabbit.get_queue_items()
        @time_out(5)
        def send_msg_with_timeout():
            version = rpc.call(context.get_admin_context(), "guest.host",
                      {"method": "version",
                       "args": {"package_name": "dpkg"}
                      })
            return { "status":"good", "version": version }
        try:
            return send_msg_with_timeout()
        except Exception as e:
            # If the Python side works, we should at least see an item waiting
            # in the queue.
            # Whether we see this determines if the failure to send is Nova's
            # fault or Sneaky Petes.
            print("Error making RPC call: %s" % e)
            print("Original queue count = %d, "
                  "current count = %d" % (original_queue_count,
                                          self.rabbit.get_queue_items()))

            # In the Kombu driver there is a bug where after restarting rabbit
            # the first message to be sent fails with a broken pipe. So here we
            # tolerate one such bug but no more.
            if not isinstance(e, TimeoutError):
                self.send_after_reconnect_errors += 1
                if self.send_after_reconnect_errors > self.tolerated_send_errors:
                    fail("Exception while making RPC call: %s" % e)
            if self.rabbit.get_queue_items() > original_queue_count:
                return { "status":"bad", "blame":"agent"}
            else:
                return { "status":"bad", "blame":"host"}

    def _send_allow_for_host_bug(self):
        while True:
            result = self._send()
            if result['status'] == "good":
                return result["version"]
            else:
                if result['blame'] == "agent":
                    fail("Nova Host put a message on the queue but the agent "
                         "never responded.")

    @test
    def check_agent_path_is_correct(self):
        """Make sure the agent binary listed in the config is correct."""
        self.agent_bin = str(test_config.values["agent_bin"])
        nova_conf = str(test_config.values["nova_conf"])
        assert_true(path.exists(self.agent_bin),
                    "Agent not found at path: %s" % self.agent_bin)
        self.agent = Service(cmd=[self.agent_bin,  "--flagfile=%s" % nova_conf,
                                  "--rabbit_reconnect_wait_time=1"])

    @test(depends_on=[check_agent_path_is_correct])
    def make_sure_we_can_identify_an_agent_failure(self):
        # This is so confusing, but it has to be, so listen up:
        # Nova code has issues sending messages so we either don't test this
        # or make allowances for Kombu's bad behavior. This test runs before
        # we start the agent and makes sure if Nova successfully sends a
        # message and the agent never answers it this test can identify that
        # and fail.
        result = self._send()
        assert_equal(result['status'], 'bad')
        assert_equal(result['blame'], 'agent')

    @test(depends_on=[make_sure_we_can_identify_an_agent_failure])
    def stop_rabbit(self):
        if self.rabbit.is_alive:
            self.rabbit.stop()
        assert_false(self.rabbit.is_alive)
        self.rabbit.reset()

    @test(depends_on=[check_agent_path_is_correct, stop_rabbit])
    def start_agent(self):
        """Starts the agent as rabbit is stopped.

        Checks to make sure the agent doesn't just give up if it can't connect
        to Rabbit, and also that the memory doesn't grow as it increasingly
        creates connections.

        """
        self.agent.start()
        mem = self.agent.get_memory_info()
        self.original_mapped = mem.mapped

    @test(depends_on=[start_agent])
    def memory_should_not_increase_as_amqp_login_fails(self):
        """The agent should not spend memory on failed connections."""
        #TODO(tim.simpson): This operates on the assumption that the the agent
        # will try to reconnect multiple times while we sleep.
        # Explanation: the syslog (where the agent logs now reside) is
        # unreadable by the test user, so we can't count the original
        # failures and wait until we know the agent has tried to reconnect
        # several times before testing again. Instead we just sleep.
        # Once we log to a readable file we should fix that.
        #self.original_fail_count = count_message_occurrence_in_file(
        #    "/var/log/syslog", "Error establishing AMQP connection"
        #)
        # Memory should not go up as the connection fails.
        print("Original mapped memory        : %d" % self.original_mapped)

        # I've noticed that the memory jumps up a bit between 5 and 10 seconds
        # after it starts and then holds steady. So instead of taking the
        # original count, let's wait a bit and use that.
        time.sleep(10)
        self.original_mapped = self.agent.get_memory_info().mapped
        print("Mapped memory at 10 seconds   : %d" % self.original_mapped)

        total_seconds = 0
        mapped = []
        for i in range(4):
            time.sleep(5)
            total_seconds += 5
            mapped.append(self.agent.get_memory_info().mapped)
            print("Mapped memory after %d seconds : %d"
                  % (total_seconds, mapped[-1]))
        if self.original_mapped < mapped[-1]:
            fail("Oh no, after %d seconds memory rose from %d to %d!"
                 % (total_seconds, self.original_mapped, mapped[-1]))
        if mapped[-1] > 30 * 1024:
            fail("Whoa, why is mapped memory = %d for procid=%d, proc= %s?"
                 % (current_mapped, self.agent.find_proc_id(), self.agent_bin))

    @test(depends_on=[memory_should_not_increase_as_amqp_login_fails])
    def start_rabbit(self):
        """Start rabbit."""
        self.rabbit.start()
        assert_true(self.rabbit.is_alive)

    @test(depends_on=[start_rabbit])
    @time_out(30)
    def send_message(self):
        """Tests that the agent auto-connects to rabbit and gets a message."""
        version = self._send_allow_for_host_bug()
        assert_true(version is not None)
        matches = re.search("(\\w+)\\.(\\w+)\\.(\\w+)\\.(\\w+)", version)
        assert_true(matches is not None)

    @test(depends_on=[send_message])
    def restart_rabbit_again(self):
        """Now stop and start rabbit, ensuring the agent reconnects."""
        self.rabbit.stop()
        assert_false(self.rabbit.is_alive)
        self.rabbit.reset()
        self.rabbit.start()
        assert_true(self.rabbit.is_alive)

    @test(depends_on=[restart_rabbit_again])
    @time_out(30)
    def send_message_again_1(self):
        """Sends a message."""
        self.tolerated_send_errors = 1
        self.send_message()

    @test(depends_on=[send_message_again_1])
    @time_out(30)
    def send_message_again_2a(self):
        """The agent should be able to receive messages after reconnecting."""
        self.send_message()

    @test(depends_on=[send_message_again_1])
    @time_out(30)
    def send_message_again_2b(self):
        """The agent should be able to receive messages after reconnecting."""
        self.send_message()




