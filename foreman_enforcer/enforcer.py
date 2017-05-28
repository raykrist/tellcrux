""" Foreman enforcer """
import logging
import os
import sys
import requests
from foreman.client import Foreman
import foreman_enforcer.resources
import tellcrux.utils as utils

class Client(object):
    """ Enforcer client """

    api_version = 2
    RESOURCES = dict()
    RESOURCES['compute_profiles'] = 'default_resource'
    RESOURCES['compute_resources'] = 'compute_resources'
    RESOURCES['compute_attributes'] = 'compute_attributes'

    #RESOURCES['operatingsystems'] = 'default_resource'

    def __init__(self, configfile, foreman_client=None, log=None):
        if log:
            self.log = log
        else:
            self.log = logging.getLogger(__name__)
        self.config = utils.load_config_yaml(configfile, log)
        self.configfile = configfile
        # Setup the foreman client
        if not foreman_client:
            self.__get_client()
        else:
            self.foreman = foreman_client
        self.log.info('connection ok')

    def load_config(self, resource):
        """ Load config for resource to enforce """
        try:
            config_dir = self.config['foreman']['config_dir']
        except KeyError:
            self.log.warn('config_dir not found in %s', self.configfile)
            return None
        resourcefile = os.path.join(config_dir, resource + '.yaml')
        self.log.debug('loading %s for resource %s', resourcefile, resource)
        return utils.load_config_yaml(resourcefile, self.log)

    def enforce_all(self, dry_run=False):
        """ Enforce all resources """
        self.log.info('Enforce all resources')
        for resource, controller in self.RESOURCES.iteritems():
            self.enforce(resource, controller, dry_run)

    def enforce(self, resource, controller='default_resource', dry_run=False):
        """ Enforce resource """
        resources = self.load_config(resource)
        self.log.info('Enforce %s', resource)
        if not resources or resource not in resources:
            self.log.warn('Could not find %s in %s.yaml', resource, resource)
            self.log.error('Noting to enforce for %s!', resource)
            return
        resource_class = getattr(foreman_enforcer.resources, controller)
        obj = resource_class(resource, self.config, self.foreman, self.log)
        obj.set_dry_run(dry_run)
        obj.update(resources)

    def __get_client(self):
        try:
            url = self.config['foreman']['url']
            username = self.config['foreman']['username']
            password = self.config['foreman']['password']
        except KeyError:
            self.log.error('missing url, username or password in %s', self.configfile)
            sys.exit(1)
        try:
            self.foreman = Foreman(url=url,
                                   auth=(username, password),
                                   api_version=self.api_version,
                                   verify=False)
        except requests.exceptions.ConnectionError as exc:
            self.log.error(exc)
            sys.exit(1)
