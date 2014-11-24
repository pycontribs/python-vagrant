'''
Python bindings for working with Vagrant and Vagrantfiles.  Do useful things
with the `vagrant` CLI without the boilerplate (and errors) of calling
`vagrant` and parsing the results.

The API attempts to conform closely to the API of the `vagrant` command line,
including method names and parameter names.

Documentation of usage, testing, installation, etc., can be found at
https://github.com/todddeluca/python-vagrant.
'''

import collections
import os
import re
import subprocess
import sys
import logging


# python package version
# should match r"^__version__ = '(?P<version>[^']+)'$" for setup.py
__version__ = '0.5.1'


log = logging.getLogger(__name__)


VAGRANT_NOT_FOUND_WARNING = 'The Vagrant executable cannot be found. ' \
                            'Please check if it is in the system path.'


def which(program):
    '''
    Emulate unix 'which' command.  If program is a path to an executable file
    (i.e. it contains any directory components, like './myscript'), return
    program.  Otherwise, if an executable file matching program is found in one
    of the directories in the PATH environment variable, return the first match
    found.

    On Windows, if PATHEXT is defined and program does not include an
    extension, include the extensions in PATHEXT when searching for a matching
    executable file.

    Return None if no executable file is found.

    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python/377028#377028
    https://github.com/webcoyote/vagrant/blob/f70507062e3b30c00db1f0d8b90f9245c4c997d4/lib/vagrant/util/file_util.rb
    Python3.3+ implementation:
    https://hg.python.org/cpython/file/default/Lib/shutil.py
    '''
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    # Shortcut: If program contains any dir components, do not search the path
    # e.g. './backup', '/bin/ls'
    if os.path.dirname(program):
        if is_exe(program):
            return program
        else:
            return None

    # Are we on windows?
    # http://stackoverflow.com/questions/1325581/how-do-i-check-if-im-running-on-windows-in-python
    windows = (os.name == 'nt')
    # Or cygwin?
    # https://docs.python.org/2/library/sys.html#sys.platform
    cygwin = sys.platform.startswith('cygwin')

    # Paths: a list of directories
    path_str = os.environ.get('PATH', os.defpath)
    if not path_str:
        paths = []
    else:
        paths = path_str.split(os.pathsep)
    # The current directory takes precedence on Windows.
    if windows:
        paths.insert(0, os.curdir)

    # Only search PATH if there is one to search.
    if not paths:
        return None

    # Files: add any necessary extensions to program
    # On cygwin and non-windows systems do not add extensions when searching
    # for the executable
    if cygwin or not windows:
        files = [program]
    else:
        # windows path extensions in PATHEXT.
        # e.g. ['.EXE', '.CMD', '.BAT']
        # http://environmentvariables.org/PathExt
        # This might not properly use extensions that have been "registered" in
        # Windows. In the future it might make sense to use one of the many
        # "which" packages on PyPI.
        exts = os.environ.get('PATHEXT', '').split(os.pathsep)

        # if the program ends with one of the extensions, only test that one.
        # otherwise test all the extensions.
        matching_exts = [ext for ext in exts if
                         program.lower().endswith(ext.lower())]
        if matching_exts:
            files = [program + ext for ext in matching_exts]
        else:
            files = [program + ext for ext in exts]

    # Check each combination of path, program, and extension, returning
    # the first combination that exists and is executable.
    for path in paths:
        for f in files:
            fpath = os.path.normcase(os.path.join(path, f))
            if is_exe(fpath):
                return fpath

    return None


# The full path to the vagrant executable, e.g. '/usr/bin/vagrant'
def get_vagrant_executable():
    return which('vagrant')


if get_vagrant_executable() is None:
    log.warn(VAGRANT_NOT_FOUND_WARNING)


# Classes for listings of Statuses, Boxes, and Plugins
Status = collections.namedtuple('Status', ['name', 'state', 'provider'])
Box = collections.namedtuple('Box', ['name', 'provider', 'version'])
Plugin = collections.namedtuple('Plugin', ['name', 'version', 'system'])


class Vagrant(object):
    '''
    Object to up (launch) and destroy (terminate) vagrant virtual machines,
    to check the status of the machine and to report on the configuration
    of the machine.

    Works by using the `vagrant` executable and a `Vagrantfile`.
    '''
    # statuses
    RUNNING = 'running'  # vagrant up
    NOT_CREATED = 'not created'  # vagrant destroy
    POWEROFF = 'poweroff'  # vagrant halt
    ABORTED = 'aborted'  # The VM is in an aborted state
    SAVED = 'saved' # vagrant suspend
    # LXC statuses
    STOPPED = 'stopped'
    FROZEN = 'frozen'

    STATUSES = (RUNNING, NOT_CREATED, POWEROFF, ABORTED, SAVED, STOPPED, FROZEN)

    BASE_BOXES = {
        'ubuntu-Lucid32': 'http://files.vagrantup.com/lucid32.box',
        'ubuntu-lucid32': 'http://files.vagrantup.com/lucid32.box',
        'ubuntu-lucid64': 'http://files.vagrantup.com/lucid64.box',
        'ubuntu-precise32': 'http://files.vagrantup.com/precise32.box',
        'ubuntu-precise64': 'http://files.vagrantup.com/precise64.box',
    }

    def __init__(self, root=None, quiet_stdout=True, quiet_stderr=True):
        '''
        root: a directory containing a file named Vagrantfile.  Defaults to
        os.getcwd(). This is the directory and Vagrantfile that the Vagrant
        instance will operate on.
        quiet_stdout: If True, the stdout of vagrant commands whose output is
          not captured for further processing will be sent to devnull.
        quiet_stderr: If True, the stderr of vagrant commands whose output is
          not captured for further processing will be sent to devnull.
        '''
        self.root = os.path.abspath(root) if root is not None else os.getcwd()
        self._cached_conf = {}
        self._vagrant_exe = None # cache vagrant executable path
        self.quiet_stdout = quiet_stdout
        self.quiet_stderr = quiet_stderr

    def version(self):
        '''
        Return the installed vagrant version, as a string, e.g. '1.5.0'
        '''
        output = self._run_vagrant_command(['--version'])
        m = re.search(r'^Vagrant (?P<version>.+)$', output)
        if m is None:
            raise Exception('Failed to parse vagrant --version output. output={!r}'.format(output))
        return m.group('version')

    def init(self, box_name=None, box_url=None):
        '''
        From the Vagrant docs:

        This initializes the current directory to be a Vagrant environment by
        creating an initial Vagrantfile if one doesn't already exist.

        If box_name is given, it will prepopulate the config.vm.box setting in
        the created Vagrantfile.
        If box_url is given, it will prepopulate the config.vm.box_url setting
        in the created Vagrantfile.

        Note: if box_url is given, box_name should also be given.
        '''
        self._call_vagrant_command(['init', box_name, box_url])

    def up(self, no_provision=False, provider=None, vm_name=None,
           provision=None, provision_with=None):
        '''
        Launch the Vagrant box.
        provision_with: optional list of provisioners to enable.
        provider: Back the machine with a specific provider
        no_provision: if True, disable provisioning.  Same as 'provision=False'.
        provision: optional boolean.  Enable or disable provisioning.  Default
          behavior is to use the underlying vagrant default.
        Note: If provision and no_provision are not None, no_provision will be
        ignored.
        '''
        provider_arg = '--provider=%s' % provider if provider else None
        prov_with_arg = None if provision_with is None else '--provision-with'
        providers_arg = None if provision_with is None else ','.join(provision_with)

        # For the sake of backward compatibility, no_provision is allowed.
        # However it is ignored if provision is set.
        if provision is not None:
            no_provision = None
        no_provision_arg = '--no-provision' if no_provision else None
        provision_arg = None if provision is None else '--provision' if provision else '--no-provision'

        self._call_vagrant_command(['up', vm_name, no_provision_arg,
                                   provision_arg, provider_arg,
                                   prov_with_arg, providers_arg])
        try:
            self.conf(vm_name=vm_name)  # cache configuration
        except subprocess.CalledProcessError:
            # in multi-VM environments, up() can be used to start all VMs,
            # however vm_name is required for conf() or ssh_config().
            pass

    def provision(self, vm_name=None, provision_with=None):
        '''
        Runs the provisioners defined in the Vagrantfile.
        vm_name: optional VM name string.
        provision_with: optional list of provisioners to enable.
          e.g. ['shell', 'chef_solo']
        '''
        prov_with_arg = None if provision_with is None else '--provision-with'
        providers_arg = None if provision_with is None else ','.join(provision_with)
        self._call_vagrant_command(['provision', vm_name, prov_with_arg,
                                   providers_arg])

    def reload(self, vm_name=None, provision=None, provision_with=None):
        '''
        Quoting from Vagrant docs:
        > The equivalent of running a halt followed by an up.

        > This command is usually required for changes made in the Vagrantfile to take effect. After making any modifications to the Vagrantfile, a reload should be called.

        > The configured provisioners will not run again, by default. You can force the provisioners to re-run by specifying the --provision flag.

        provision: optional boolean.  Enable or disable provisioning.  Default
          behavior is to use the underlying vagrant default.
        provision_with: optional list of provisioners to enable.
          e.g. ['shell', 'chef_solo']
        '''
        prov_with_arg = None if provision_with is None else '--provision-with'
        providers_arg = None if provision_with is None else ','.join(provision_with)
        provision_arg = None if provision is None else '--provision' if provision else '--no-provision'
        self._call_vagrant_command(['reload', vm_name, provision_arg,
                                   prov_with_arg, providers_arg])

    def suspend(self, vm_name=None):
        '''
        Suspend/save the machine.
        '''
        self._call_vagrant_command(['suspend', vm_name])
        self._cached_conf[vm_name] = None  # remove cached configuration

    def halt(self, vm_name=None, force=False):
        '''
        Halt the Vagrant box.

        force: If True, force shut down.
        '''
        force_opt = '--force' if force else None
        self._call_vagrant_command(['halt', vm_name, force_opt])
        self._cached_conf[vm_name] = None  # remove cached configuration

    def destroy(self, vm_name=None):
        '''
        Terminate the running Vagrant box.
        '''
        self._call_vagrant_command(['destroy', vm_name, '--force'])
        self._cached_conf[vm_name] = None  # remove cached configuration

    def status(self, vm_name=None):
        '''
        Return the results of a `vagrant status` call as a list of one or more
        Status objects.  A Status contains the following attributes:

        - name: The VM name in a multi-vm environment.  'default' otherwise.
        - state: The state of the underlying guest machine (i.e. VM).
        - provider: the name of the VM provider, e.g. 'virtualbox'.  None
          if no provider is output by vagrant.

        This information corresponds with the current return values from running
        `vagrant status`, as of Vagrant 1.5.

        Example return values for a multi-VM environment:

            [Status(name='web', state='not created', provider='virtualbox'),
             Status(name='db', state='not created', provider='virtualbox')]

        And for a single-VM environment:

            [Status(name='default', state='not created', provider='virtualbox')]

        Possible states include, but are not limited to (since new states are
        being added as Vagrant evolves):

        - 'not created' if the vm is destroyed
        - 'running' if the vm is up
        - 'poweroff' if the vm is halted
        - 'saved' if the vm is suspended
        - 'aborted' if the vm is aborted
        - None if no status is found

        As of Vagrant 1.1.0, vagrant has started supporting providers (like
        virtualbox and vmware_fusion) and has started adding the provider in
        the status string, like 'not created (virtualbox)'.

        Implementation notes:

        - The human-readable output of vagrant lists the vm name as 'default'
          in a single vm environment.  This is in contrast to the
          Machine-readable output from vagrant, which lists the vm name
          (a.k.a. target) as '' in a single VM environment.
        - The human readable states differ from machine readable states.  For
          example, 'not created' versus 'not_created'.  In order to future-proof
          code using python-vagrant, use the status constants defined in the
          Vagrant class instead of hardcoding the string.  At some point
          parsing will switch from using the human-readable output to the
          machine readable output and the state values might change as well.
        '''
        # example output (without provdier):
        # Current VM states:
        #
        # default                  poweroff
        #
        # The VM is powered off. To restart the VM, simply run `vagrant up`

        # example multi-VM environment output (with provider):
        # Current machine states:
        #
        # web                       not created (virtualbox)
        # db                        not created (virtualbox)
        #
        # This environment represents multiple VMs. The VMs are all listed
        # above with their current state. For more information about a specific
        # VM, run `vagrant status NAME`.

        output = self._run_vagrant_command(['status', vm_name])
        # The format of output is expected to be a
        #   - "Current VM states:" line (vagrant 1)
        #   - "Current machine states" line (vagrant 1.1)
        # followed by a blank line, followed by one or more status lines,
        # followed by a blank line.

        # Parsing the output of `vagrant status`
        # Currently parsing is constrained to known states.  Otherwise how
        # could we know where the VM name ends and the state begins.
        # Once --machine-readable output is stable (a work in progress as of
        # Vagrant 1.5), this constraint can be lifted.
        START_LINE, FIRST_BLANK, VM_STATUS = 1, 2, 3
        statuses = []
        parse_state = START_LINE # looking for for the 'Current ... states' line
        for line in output.splitlines():
            line = line.strip()
            if parse_state == START_LINE and re.search('^Current (VM|machine) states:', line):
                parse_state = FIRST_BLANK # looking for the first blank line
            elif parse_state == FIRST_BLANK and not line:
                parse_state = VM_STATUS # looking for machine status lines
            elif parse_state == VM_STATUS and line:
                vm_name_and_state, provider = self._parse_provider_line(line)
                # Split vm_name from status.  Only works for recognized states.
                m = re.search(r'^(?P<vm_name>.*?)\s+(?P<state>' +
                              '|'.join(self.STATUSES) + ')$',
                              vm_name_and_state)
                if not m:
                    raise Exception('ParseError: Failed to properly parse vm name and status from line.',
                                    line, output)
                else:
                    status = Status(m.group('vm_name'), m.group('state'), provider)
                    statuses.append(status)
            elif parse_state == VM_STATUS and not line:
                # Found the second blank line.  All done.
                break

        return statuses

    def conf(self, ssh_config=None, vm_name=None):
        '''
        Parse ssh_config into a dict containing the keys defined in ssh_config,
        which should include these keys (listed with example values): 'User'
        (e.g.  'vagrant'), 'HostName' (e.g. 'localhost'), 'Port' (e.g. '2222'),
        'IdentityFile' (e.g. '/home/todd/.ssh/id_dsa').  Cache the parsed
        configuration dict.  Return the dict.

        If ssh_config is not given, return the cached dict.  If there is no
        cached configuration, call ssh_config() to get the configuration, then
        parse, cache, and return the config dict.  Calling ssh_config() raises
        an Exception if the Vagrant box has not yet been created or has been
        destroyed.

        vm_name: required in a Multi-VM Vagrant environment.  This name will be
        used to get the configuration for the named vm and associate the config
        with the vm name in the cache.

        ssh_config: a valid ssh confige file host section.  Defaults to
        the value returned from ssh_config().  For speed, the configuration
        parsed from ssh_config is cached for subsequent calls.
        '''
        if self._cached_conf.get(vm_name) is None or ssh_config is not None:
            if ssh_config is None:
                ssh_config = self.ssh_config(vm_name=vm_name)
            conf = self._parse_config(ssh_config)
            self._cached_conf[vm_name] = conf

        return self._cached_conf[vm_name]

    def ssh_config(self, vm_name=None):
        '''
        Return the output of 'vagrant ssh-config' which appears to be a valid
        Host section suitable for use in an ssh config file.
        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.

        vm_name: required in a multi-VM environment.

        Example output:
            Host default
                HostName 127.0.0.1
                User vagrant
                Port 2222
                UserKnownHostsFile /dev/null
                StrictHostKeyChecking no
                PasswordAuthentication no
                IdentityFile /Users/todd/.vagrant.d/insecure_private_key
                IdentitiesOnly yes
        '''
        # capture ssh configuration from vagrant
        return self._run_vagrant_command(['ssh-config', vm_name])

    def user(self, vm_name=None):
        '''
        Return the ssh user of the vagrant box, e.g. 'vagrant'
        or None if there is no user in the ssh_config.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        return self.conf(vm_name=vm_name).get('User')

    def hostname(self, vm_name=None):
        '''
        Return the vagrant box hostname, e.g. '127.0.0.1'
        or None if there is no hostname in the ssh_config.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        return self.conf(vm_name=vm_name).get('HostName')

    def port(self, vm_name=None):
        '''
        Return the vagrant box ssh port, e.g. '2222'
        or None if there is no port in the ssh_config.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        return self.conf(vm_name=vm_name).get('Port')

    def keyfile(self, vm_name=None):
        '''
        Return the path to the private key used to log in to the vagrant box
        or None if there is no keyfile (IdentityFile) in the ssh_config.
        E.g. '/Users/todd/.vagrant.d/insecure_private_key'

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.

        KeyFile is a synonym for IdentityFile.
        '''
        return self.conf(vm_name=vm_name).get('IdentityFile')

    def user_hostname(self, vm_name=None):
        '''
        Return a string combining user and hostname, e.g. 'vagrant@127.0.0.1'.
        This string is suitable for use in an ssh commmand.  If user is None
        or empty, it will be left out of the string, e.g. 'localhost'.  If
        hostname is None, have bigger problems.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        user = self.user(vm_name=vm_name)
        user_prefix = user + '@' if user else ''
        return user_prefix + self.hostname(vm_name=vm_name)

    def user_hostname_port(self, vm_name=None):
        '''
        Return a string combining user, hostname and port, e.g.
        'vagrant@127.0.0.1:2222'.  This string is suitable for use with Fabric,
        in env.hosts.  If user or port is None or empty, they will be left
        out of the string.  E.g. 'vagrant@localhost', or 'localhost:2222' or
        'localhost'.  If hostname is None, you have bigger problems.


        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        user = self.user(vm_name=vm_name)
        port = self.port(vm_name=vm_name)
        user_prefix = user + '@' if user else ''
        port_suffix = ':' + port if port else ''
        return user_prefix + self.hostname(vm_name=vm_name) + port_suffix

    def box_add(self, name, url, provider=None, force=False):
        '''
        Adds a box with given name, from given url.

        force: If True, overwrite an existing box if it exists.
        '''
        force_opt = '--force' if force else None
        cmd = ['box', 'add', name, url, force_opt]
        if provider is not None:
            cmd += ['--provider', provider]

        self._call_vagrant_command(cmd)

    def box_list(self):
        '''
        Run `vagrant box list` and return a list of Box objects containing the
        results.  A Box object has the following attributes:

        - name: the box-name.
        - provider: the box-provider.
        - version: the box-version.

        Example output:

            [Box(name='precise32', provider='virtualbox', version=None),
             Box(name='precise64', provider='virtualbox', version=None),
             Box(name='trusty64', provider='virtualbox', version=None)]

        Implementation Notes:

        - The box-version is not currently returned, since we parse the
          human-readable vagrant output, where it is not listed.  As of Vagrant
          1.5 (or 1.4?) is is available in the --machine-readable output.
          Once parsing is switched to use that output, it will be available.
        - As of Vagrant >= 1.1, boxes are listed with names and providers.
        '''
        output = self._run_vagrant_command(['box', 'list'])
        boxes = []
        for line in output.splitlines():
            name, provider = self._parse_provider_line(line)
            box = Box(name, provider, version=None) # not currently parsing the box version
            boxes.append(box)
        return boxes

    def box_remove(self, name, provider):
        '''
        Removes the box matching name and provider. It is an error if no box
        matches name and provider.
        '''
        self._call_vagrant_command(['box', 'remove', name, provider])

    def plugin_list(self):
        '''
        Return a list of Plugin objects containing the following information
        about installed plugins:

        - name: The plugin name, as a string.
        - version: The plugin version, as a string.
        - system: A boolean, presumably indicating whether this plugin is a
          "core" part of vagrant, though the feature is not yet documented
          in the Vagrant 1.5 docs.

        Example output:

            [Plugin(name='sahara', version='0.0.16', system=False),
             Plugin(name='vagrant-login', version='1.0.1', system=True),
             Plugin(name='vagrant-share', version='1.0.1', system=True)]
        '''
        output = self._run_vagrant_command(['plugin', 'list'])
        return [self._parse_plugin_list_line(l) for l in output.splitlines()]

    def _parse_plugin_list_line(self, line):
        # As of Vagrant 1.5, the format of the `vagrant plugin list` command can
        # be inferred here:
        # https://github.com/mitchellh/vagrant/blob/master/plugins/commands/plugin/action/list_plugins.rb#L35
        # Example plugin listing lines:
        # sahara (0.0.16)
        # vagrant-login (1.0.1, system)
        regex = re.compile(r'^(?P<name>.+?)\s+\((?P<version>.+?)(?P<system>, system)?\)$')
        m = regex.search(line)
        if m is None:
            raise Exception('Error parsing plugin listing line.', line)
        else:
            return Plugin(m.group('name'), m.group('version'), bool(m.group('system')))

    def _parse_provider_line(self, line):
        '''
        In vagrant 1.1+, `vagrant box list` produces lines like:

            precise32                (virtualbox)

        And `vagrant status` produces lines like:

            default                  not created (virtualbox)

        Pre-1.1 version of vagrant produce lines without a provider
        in parentheses.  This helper function separates the beginning of the
        line from the provider at the end of the line.  It assumes that the
        provider is surrounded by parentheses (and contains no parentheses.
        It returns the beginning of the line (trimmed of whitespace) and
        the provider (or None if the line has no provider).

        Example outputs:

            ('precise32', 'virtualbox')
            ('default                  not created', 'virtualbox')
        '''
        m = re.search(r'^\s*(?P<value>.+?)\s+\((?P<provider>[^)]+)\)\s*$',
                          line)
        if m:
            return m.group('value'), m.group('provider')
        else:
            return line.strip(), None

    def _parse_config(self, ssh_config):
        '''
        This lame parser does not parse the full grammar of an ssh config
        file.  It makes assumptions that are (hopefully) correct for the output
        of `vagrant ssh-config [vm-name]`.  Specifically it assumes that there
        is only one Host section, the default vagrant host.  It assumes that
        the parameters of the ssh config are not changing.
        every line is of the form 'key  value', where key is a single token
        without any whitespace and value is the remaining part of the line.
        Value may optionally be surrounded in double quotes.  All leading and
        trailing whitespace is removed from key and value.  Example lines:

        '    User vagrant\n'
        '    IdentityFile "/home/robert/.vagrant.d/insecure_private_key"\n'

        Lines with '#' as the first non-whitespace character are considered
        comments and ignored.  Whitespace-only lines are ignored.  This parser
        does NOT handle using an '=' in options.  Values surrounded in double
        quotes will have the double quotes removed.

        See https://github.com/bitprophet/ssh/blob/master/ssh/config.py for a
        more compliant ssh config file parser.
        '''
        conf = dict()
        started_parsing = False
        for line in ssh_config.splitlines():
            if line.strip().startswith('Host ') and not started_parsing:
                started_parsing = True
            if not started_parsing or not line.strip() or line.strip().startswith('#'):
                continue
            key, value = line.strip().split(None, 1)
            # Remove leading and trailing " from the values
            conf[key] = value.strip('"')
        return conf

    def _make_vagrant_command(self, args):
        if self._vagrant_exe is None:
            self._vagrant_exe = get_vagrant_executable()

        if not self._vagrant_exe:
            raise RuntimeError(VAGRANT_NOT_FOUND_WARNING)

        # filter out None args.  Since vm_name is None in non-Multi-VM
        # environments, this quitely removes it from the arguments list
        # when it is not specified.
        return [self._vagrant_exe] + [arg for arg in args if arg is not None]

    def _call_vagrant_command(self, args):
        '''
        Run a vagrant command.  Return None.
        args: A sequence of arguments to a vagrant command line.

        '''
        # Make subprocess command
        command = self._make_vagrant_command(args)
        if self.quiet_stdout or self.quiet_stderr:
            # Redirect stdout and/or stderr to devnull
            # Use with stmt to close filehandle in case of exception
            with open(os.devnull, 'wb') as fh:
                outfh = fh if self.quiet_stdout else sys.stdout
                errfh = fh if self.quiet_stderr else sys.stderr
                subprocess.check_call(command, cwd=self.root,
                                      stdout=outfh, stderr=errfh)
        else:
            subprocess.check_call(command, cwd=self.root)

    def _run_vagrant_command(self, args):
        '''
        Run a vagrant command and return its stdout.
        args: A sequence of arguments to a vagrant command line.
        e.g. ['up', 'my_vm_name', '--no-provision'] or
        ['up', None, '--no-provision'] for a non-Multi-VM environment.
        '''
        # Make subprocess command
        command = self._make_vagrant_command(args)
        return subprocess.check_output(command, cwd=self.root)


class SandboxVagrant(Vagrant):
    '''
    Support for sandbox mode using the Sahara gem (https://github.com/jedi4ever/sahara).
    '''

    def _run_sandbox_command(self, args):
        return self._run_vagrant_command(['sandbox'] + list(args))

    def sandbox_commit(self, vm_name=None):
        '''
        Permanently writes all the changes made to the VM.
        '''
        self._run_sandbox_command(['commit', vm_name])

    def sandbox_off(self, vm_name=None):
        '''
        Disables the sandbox mode.
        '''
        self._run_sandbox_command(['off', vm_name])

    def sandbox_on(self, vm_name=None):
        '''
        Enables the sandbox mode.

        This requires the Sahara gem to be installed
        (https://github.com/jedi4ever/sahara).
        '''
        self._run_sandbox_command(['on', vm_name])

    def sandbox_rollback(self, vm_name=None):
        '''
        Reverts all the changes made to the VM since the last commit.
        '''
        self._run_sandbox_command(['rollback', vm_name])

    def sandbox_status(self, vm_name=None):
        '''
        Returns the status of the sandbox mode.

        Possible values are:
        - on
        - off
        - unknown
        - not installed
        '''
        vagrant_sandbox_output = self._run_sandbox_command(['status', vm_name])
        return self._parse_vagrant_sandbox_status(vagrant_sandbox_output)

    def _parse_vagrant_sandbox_status(self, vagrant_output):
        '''
        Returns the status of the sandbox mode given output from
        'vagrant sandbox status'.
        '''
        # typical output
        # [default] - snapshot mode is off
        # or
        # [default] - machine not created
        # if the box VM is down
        tokens = [token.strip() for token in vagrant_output.split(' ')]
        if tokens[0] == 'Usage:':
            sahara_status = 'not installed'
        elif "{} {}".format(tokens[-2], tokens[-1]) == 'not created':
            sahara_status = 'unknown'
        else:
            sahara_status = tokens[-1]
        return sahara_status
