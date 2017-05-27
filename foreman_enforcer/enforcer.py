""" Foreman enforcer """
import importlib
import logging
import os
import sys
from abc import ABCMeta, abstractmethod
import requests
from foreman.client import Foreman
import tellcrux.utils as utils


class Client(object):
    """ Enforcer client """

    api_version = 2
    RESOURCES = ['compute_resources']

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
        for resource in self.RESOURCES:
            self.enforce(resource, dry_run)

    def enforce(self, resource, dry_run=False):
        """ Enforce resource """
        resources = self.load_config(resource)
        self.log.info('Enforce %s', resource)
        if resource not in resources:
            self.log.warn('Could not find %s in %s.yaml', resource, resource)
            self.log.error('Noting to enforce for %s!', resource)
            return
        resource_class = getattr(importlib.import_module(__name__), resource)
        obj = resource_class(self.config, self.foreman, self.log)
        obj.update(resources, dry_run=dry_run)

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

class Resource(object):
    """ Foreman resource """

    __metaclass__ = ABCMeta

    def __init__(self, config, foreman, log):
        self.foreman = foreman
        self.config = config
        self.log = log
        if 'domain' in self.config['foreman']:
            self.domain = '.' + self.config['foreman']['domain']
        else:
            self.domain = ''

    def update(self, resources, dry_run=False):
        """ Updated resource """
        defaults = resources['defaults'] if 'defaults' in resources else {}
        self.log.debug("defaults for %s = %s", self.name, defaults)
        old_resources = self.get_resources()
        #print old_resources['results']
        for name, values in resources[self.name].iteritems():
            values = self.mapping(name, values)
            # If value not set for key use default value
            for k, v in defaults.iteritems():
                if k not in values:
                    values[k] = v
            if name not in old_resources:
                if dry_run:
                    self.log.info('DRY-RUN: Create %s %s', self.name, name)
                else:
                    self.create_resource(values)
            elif not self.__match(old_resources[name], values):
                if dry_run:
                    self.log.info('DRY-RUN: Update %s %s', self.name, name)
                else:
                    self.update_resource(old_resources[name]['id'], values)
            else:
                self.log.debug('No need to update %s %s ', self.name, name)

    def mapping(self, name, values):
        """ Do a value mapping for this resource type """
        values['name'] = name
        self.log.info('Values for %s = %s', name, values)
        return values

    @staticmethod
    def __match(old_resource, resource):
        """ Match resource to update with the old resource data from foreman """
        for key, value in resource.iteritems():
            if old_resource[key] != value:
                return False
        return True

    @abstractmethod
    def create_resource(self, resource):
        """ Create a new resource """
        pass

    @abstractmethod
    def update_resource(self, resource_id, resource):
        """ Update a new resource """
        pass

    @abstractmethod
    def get_resources(self):
        """ Return old resources in a dict """
        pass

class compute_resources(Resource):
    """ Compute resources """

    def __init__(self, config, foreman, log):
        super(compute_resources, self).__init__(config, foreman, log)
        self.name = type(self).__name__

    def mapping(self, name, values):
        """ Do a value mapping for this resource type """
        values['name'] = name
        if not 'url' in values:
            values['url'] = 'qemu+tcp://%s%s:16509/system' % (name, self.domain)
        self.log.info('Values for %s = %s', name, values)
        return values

    def create_resource(self, resource):
        """ Create a new resource """
        result = self.foreman.create_computeresources(resource)
        self.log.debug("Created new %s with name %s", self.name, result['name'])
        return result

    def update_resource(self, resource_id, resource):
        """ Update a new resource """
        result = self.foreman.update_computeresources(resource_id, resource)
        self.log.debug("Updated %s with name %s", self.name, resource['name'])
        return result

    def get_resources(self):
        """ Return old resources in a dict """
        results = self.foreman.index_computeresources()
        resources = dict()
        if 'results' not in results:
            return resources
        for result in results['results']:
            resources[result['name']] = result
            self.log.info('Get old values for %s %s', self.name, result['name'])
        return resources
