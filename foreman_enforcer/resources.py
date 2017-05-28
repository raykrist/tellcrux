""" Collection of foreman resource classes """

from abc import ABCMeta#, abstractmethod
import pprint

class Resource(object):
    """ Foreman resource """

    __metaclass__ = ABCMeta

    def __init__(self, name, config, foreman, log):
        self.name = name
        self.dry_run = False
        self.foreman = foreman
        self.config = config
        self.log = log
        if 'domain' in self.config['foreman']:
            self.domain = '.' + self.config['foreman']['domain']
        else:
            self.domain = ''

    def set_dry_run(self, dry_run):
        """ Turn on/off DRY-RUN for all actions """
        self.dry_run = True if dry_run else False

    def update(self, resources):
        """ Updated resource """
        defaults = resources['defaults'] if 'defaults' in resources else {}
        self.log.debug("defaults for %s = %s", self.name, defaults)
        current = self.get_resources()
        for name, values in resources[self.name].iteritems():
            resource_values = self.mapping(name, values)
            values = self._merge(defaults, resource_values)
            if name not in current:
                self.create_resource(name, values)
            elif not self._match(current[name], values):
                self.update_resource(name, current[name]['id'], values)
            else:
                self.log.debug('No need to update %s %s ', self.name, name)

    def call_api(self, action, name, args):
        """ Run a API call to foreman API via the foreman client """
        function = getattr(self.foreman, action + '_' + self.name.translate(None, '_'))
        self.log.debug('%s %s with args %s', action.title(), name, args)
        if self.dry_run and action not in ['index', 'show']:
            self.log.info('DRY-RUN: %s %s %s', action.title(), self.name, name)
            return {'results': 'DRY-RUN'}
        result = function(**args)
        self.log.debug("%s %s with name %s", action.title(), self.name, name)
        return result

    def mapping(self, name, values):
        """ Do a value mapping for this resource type """
        values['name'] = name
        self.log.info('Values for %s = %s', name, values)
        return values

    #@abstractmethod
    def create_resource(self, name, resource):
        """ Create a new resource """
        # Hack to get the singular form of the resource name
        arg_name = self.name[:-1]
        return self.call_api(action='create', name=name, args={arg_name: resource})

    #@abstractmethod
    def update_resource(self, name, resource_id, resource):
        """ Update a new resource """
        # Hack to get the singular form of the resource name
        arg_name = self.name[:-1]
        args = {'id': resource_id, arg_name: resource}
        return self.call_api(action='update', name=name, args=args)

    def get_resources(self):
        """ Return old resources in a dict """
        index = getattr(self.foreman, 'index_' + self.name.translate(None, '_'))
        results = index()
        resources = dict()
        if 'results' not in results:
            return resources
        for result in results['results']:
            resources[result['name']] = result
            self.log.info('Get old values for %s %s', self.name, result['name'])
        return resources

    @staticmethod
    def _match(first, second):
        """ Return true if the second set is a subset of the first """
        for key in second:
            if key in first:
                if isinstance(first[key], dict) and isinstance(second[key], dict):
                    sub_dict = Resource._match(first[key], second[key])
                    return sub_dict
                elif first[key] != second[key]:
                    return False
            else:
                return False
        return True

    @staticmethod
    def _merge(defaults, values):
        """ Recursive merge the values with defaults """
        for key in defaults:
            if key in values:
                if isinstance(defaults[key], dict) and isinstance(values[key], dict):
                    values[key] = Resource._merge(defaults[key], values[key])
                elif defaults[key] == values[key]:
                    pass
            else:
                values[key] = defaults[key]
        return values

class default_resource(Resource):
    """ Default foreman resource """

class compute_attributes(Resource):
    """ Setup compute attributes """

    def __init__(self, name, config, foreman, log):
        super(compute_attributes, self).__init__(name, config, foreman, log)
        # compute attributes need to be run on all compute resources
        results = self.foreman.index_computeresources()
        self.compute_resources = list()
        for result in results['results']:
            self.compute_resources.append(result['id'])
        # compute attributes also needs the compute profiles
        results = self.foreman.index_computeprofiles()
        self.compute_profiles = dict()
        for result in results['results']:
            self.compute_profiles[result['name']] = result['id']

    def update(self, resources):
        """ Updated resource """
        defaults = resources['defaults'] if 'defaults' in resources else {}
        self.log.debug("defaults for %s = %s", self.name, defaults)
        current = self.get_resources()
        for name, values in resources[self.name].iteritems():
            self.log.debug('Enforce %s', name)
            resource_values = self.mapping(name, values)
            values = self._merge(defaults, resource_values)
            if name not in current:
                # We need to crate the profile frist
                warning = ('Compute profiles need to exist before we can add'
                           'compute_attributes for compute_resources!')
                self.log.warn('Could not find compute profile %s', name)
                self.log.error(warning)
                return
            # We need to do this for each compute resource
            for cr_id in self.compute_resources:
                if cr_id not in current[name]['compute_attributes']:
                    args = {'compute_profile_id': self.compute_profiles[name],
                            'compute_resource_id': cr_id,
                            'compute_attribute': values}
                    result = self.call_api('create', name, args)
                    self.log.debug('Create compute_attributes: %s', result)
                    continue
                if not self._match(current[name]['compute_attributes'][cr_id], values):
                    args = {'compute_profile_id': self.compute_profiles[name],
                            'compute_resource_id': cr_id,
                            'compute_attribute': values,
                            'id': current[name]['compute_attributes'][cr_id]['id']}
                    result = self.call_api('update', name, args)
                    self.log.debug('Update compute_attributes: %s', result)
                else:
                    self.log.debug('No need to update %s %s ', self.name, name)

    def get_resources(self):
        """ Compute attributes are part of the compute profiles but will
            not be part of index. We will need to fetch each one with show """
        resources = dict()
        for profile_id in self.compute_profiles.values():
            profile = profile = self.foreman.show_computeprofiles(profile_id)
            name = profile['name']
            resources[name] = dict()
            resources[name]['compute_attributes'] = dict()
            if not profile['compute_attributes']:
                continue
            for attr in profile['compute_attributes']:
                self.log.debug('compute_attributes for %s: %s', name, attr)
                resources[name]['compute_attributes'][attr['compute_resource_id']] = attr
        return resources

    def mapping(self, name, values):
        """ Do a value mapping for this resource type """
        return values

class compute_resources(Resource):
    """ Compute resources """

    def __init__(self, name, config, foreman, log):
        super(compute_resources, self).__init__(name, config, foreman, log)
        self.name = name

    def mapping(self, name, values):
        """ Do a value mapping for this resource type """
        # compute attributes are used by compute_attributes not resources
        if 'compute_attributes' in values:
            del values['compute_attributes']
        values['name'] = name
        if not 'url' in values:
            values['url'] = 'qemu+tcp://%s%s:16509/system' % (name, self.domain)
        self.log.info('Values for %s = %s', name, values)
        return values
