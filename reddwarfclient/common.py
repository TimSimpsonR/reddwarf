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

import os
import pickle
import sys


from reddwarfclient import Dbaas


APITOKEN = os.path.expanduser("~/.apitoken")


def get_client():
    """Load an existing apitoken if available"""
    try:
        with open(APITOKEN, 'rb') as token:
            apitoken = pickle.load(token)
            dbaas = Dbaas(apitoken._user, apitoken._apikey, apitoken._tenant,
                          apitoken._auth_url, apitoken._service_name,
                          apitoken._service_url)
            dbaas.client.auth_token = apitoken._token
            return dbaas
    except IOError:
        print "ERROR: You need to login first and get an auth token\n"
        sys.exit(1)
    except:
        print "ERROR: There was an error using your existing auth token, " \
              "please login again.\n"
        sys.exit(1)


def methods_of(obj):
    """Get all callable methods of an object that don't start with underscore
    returns a list of tuples of the form (method_name, method)"""
    result = {}
    for i in dir(obj):
        if callable(getattr(obj, i)) and not i.startswith('_'):
            result[i] = getattr(obj, i)
    return result


def print_actions(cmd, actions):
    """Print help for the command with list of options and description"""
    print ("Available actions for '%s' cmd:") % cmd
    for k, v in actions.iteritems():
        print "\t%-20s%s" % (k, v.__doc__)
    sys.exit(2)


def print_commands(commands):
    """Print the list of available commands and description"""

    print "Available commands"
    for k, v in commands.iteritems():
        print "\t%-20s%s" % (k, v.__doc__)
    sys.exit(2)


class APIToken(object):
    """A token object containing the user, apikey and token which
       is pickleable."""

    def __init__(self, user, apikey, tenant, token, auth_url, service_name,
                 service_url):
        self._user = user
        self._apikey = apikey
        self._tenant = tenant
        self._token = token
        self._auth_url = auth_url
        self._service_name = service_name
        self._service_url = service_url


class Auth(object):
    """
    Authenticate with your username and api key to get the auth token
    for future requests
    """

    def __init__(self):
        pass

    def login(self, user, apikey, tenant="dbaas", auth_url="http://localhost:5000/v1.1",
              service_name="reddwarf", service_url=None):
        """Login to retrieve an auth token to use for other api calls"""
        try:
            dbaas = Dbaas(user, apikey, tenant, auth_url=auth_url,
                          service_name=service_name, service_url=service_url)
            dbaas.authenticate()
            apitoken = APIToken(user, apikey, tenant, dbaas.client.auth_token,
                                auth_url, service_name, service_url)

            with open(APITOKEN, 'wb') as token:
                pickle.dump(apitoken, token, protocol=2)
            print apitoken._token
        except:
            print sys.exc_info()[1]
