'''
Python bindings for working with Vagrant and Vagrantfiles.  Do useful things
with the `vagrant` CLI without the boilerplate (and errors) of calling
`vagrant` and parsing the results.

The API attempts to conform closely to the API of the `vagrant` command line,
including method names and parameter names.

Documentation of usage, testing, installation, etc., can be found at
https://github.com/todddeluca/python-vagrant.
'''

# std
import collections
import contextlib
import itertools
import os
import re
import subprocess
import sys
import logging

# local
from . import compat


# python package version
# should match r"^__version__ = '(?P<version>[^']+)'$" for setup.py
__version__ = '0.5.13'


log = logging.getLogger(__name__)


###########################################
# Determine Where The Vagrant Executable Is

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


#########################################################################
# Context Managers for Handling the Output of Vagrant Subprocess Commands


@contextlib.contextmanager
def stdout_cm():
    ''' Redirect the stdout or stderr of the child process to sys.stdout. '''
    yield sys.stdout


@contextlib.contextmanager
def stderr_cm():
    ''' Redirect the stdout or stderr of the child process to sys.stderr. '''
    yield sys.stderr


@contextlib.contextmanager
def devnull_cm():
    ''' Redirect the stdout or stderr of the child process to /dev/null. '''
    with open(os.devnull, 'w') as fh:
        yield fh


@contextlib.contextmanager
def none_cm():
    ''' Use the stdout or stderr file handle of the parent process. '''
    yield None


def make_file_cm(filename, mode='a'):
    '''
    Open a file for appending and yield the open filehandle.  Close the 
    filehandle after yielding it.  This is useful for creating a context
    manager for logging the output of a `Vagrant` instance.

    filename: a path to a file
    mode: The mode in which to open the file.  Defaults to 'a', append

    Usage example:

        log_cm = make_file_cm('application.log')
        v = Vagrant(out_cm=log_cm, err_cm=log_cm)
    '''
    @contextlib.contextmanager
    def cm():
        with open(filename, mode=mode) as fh:
            yield fh

    return cm


class Vagrant(object):
    '''
    Object to up (launch) and destroy (terminate) vagrant virtual machines,
    to check the status of the machine and to report on the configuration
    of the machine.

    Works by using the `vagrant` executable and a `Vagrantfile`.
    '''

    # Some machine-readable state values returned by status
    # There are likely some missing, but if you use vagrant you should
    # know what you are looking for.
    # These exist partly for convenience and partly to document the output
    # of vagrant.
    RUNNING = 'running'  # vagrant up
    NOT_CREATED = 'not_created'  # vagrant destroy
    POWEROFF = 'poweroff'  # vagrant halt
    ABORTED = 'aborted'  # The VM is in an aborted state
    SAVED = 'saved' # vagrant suspend
    # LXC statuses
    STOPPED = 'stopped'
    FROZEN = 'frozen'
    # libvirt
    SHUTOFF = 'shutoff'

    BASE_BOXES = {
        'ubuntu-Lucid32': 'http://files.vagrantup.com/lucid32.box',
        'ubuntu-lucid32': 'http://files.vagrantup.com/lucid32.box',
        'ubuntu-lucid64': 'http://files.vagrantup.com/lucid64.box',
        'ubuntu-precise32': 'http://files.vagrantup.com/precise32.box',
        'ubuntu-precise64': 'http://files.vagrantup.com/precise64.box',
    }

    def __init__(self, root=None, quiet_stdout=True, quiet_stderr=True,
                 env=None, out_cm=None, err_cm=None):
        '''
        root: a directory containing a file named Vagrantfile.  Defaults to
        os.getcwd(). This is the directory and Vagrantfile that the Vagrant
        instance will operate on.
        env: a dict of environment variables (string keys and values) passed to
          the vagrant command subprocess or None.  Defaults to None.  If env is
          None, `subprocess.Popen` uses the current process environment.
        out_cm: a no-argument function that returns a ContextManager that
          yields a filehandle or other object suitable to be passed as the
          `stdout` parameter of a subprocess that runs a vagrant command.
          Using a context manager allows one to close the filehandle in case of
          an Exception, if necessary.  Defaults to none_cm, a context manager
          that yields None.  See `make_file_cm` for an example of
          how to log stdout to a file.  Note that commands that parse the
          output of a vagrant command, like `status`, capture output for their
          own use, ignoring the value of `out_cm` and `quiet_stdout`.
        err_cm: a no-argument function that returns a ContextManager, like
          out_cm, for handling the stderr of the vagrant subprocess.  Defaults
          to none_cm.
        quiet_stdout: Ignored if out_cm is not None.  If True, the stdout of
          vagrant commands whose output is not captured for further processing
          will be sent to devnull.
        quiet_stderr: Ignored if out_cm is not None.  If True, the stderr of
          vagrant commands whose output is not captured for further processing
          will be sent to devnull.
        '''
        self.root = os.path.abspath(root) if root is not None else os.getcwd()
        self._cached_conf = {}
        self._vagrant_exe = None # cache vagrant executable path
        self.env = env
        if out_cm is not None:
            self.out_cm = out_cm
        elif quiet_stdout:
            self.out_cm = devnull_cm
        else:
            # Using none_cm instead of stdout_cm, because in some situations,
            # e.g. using nosetests, sys.stdout is a StringIO object, not a
            # filehandle.  Also, passing None to the subprocess is consistent
            # with past behavior.
            self.out_cm = none_cm

        if err_cm is not None:
            self.err_cm = err_cm
        elif quiet_stderr:
            self.err_cm = devnull_cm
        else:
            self.err_cm = none_cm

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
        vm_name=None: name of VM.
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

    def resume(self, vm_name=None):
        '''
        Resume suspended machine.
        '''
        self._call_vagrant_command(['resume', vm_name])
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

        Example return values for a multi-VM environment:

            [Status(name='web', state='not created', provider='virtualbox'),
             Status(name='db', state='not created', provider='virtualbox')]

        And for a single-VM environment:

            [Status(name='default', state='not created', provider='virtualbox')]

        Possible states include, but are not limited to (since new states are
        being added as Vagrant evolves):

        - 'not_created' if the vm is destroyed
        - 'running' if the vm is up
        - 'poweroff' if the vm is halted
        - 'saved' if the vm is suspended
        - 'aborted' if the vm is aborted

        Implementation Details:

        This command uses the `--machine-readable` flag added in
        Vagrant 1.5,  mapping the target name, state, and provider-name
        to a Status object.

        Example with no VM name and multi-vm Vagrantfile:

            $ vagrant status --machine-readable
            1424098924,web,provider-name,virtualbox
            1424098924,web,state,running
            1424098924,web,state-human-short,running
            1424098924,web,state-human-long,The VM is running. To stop this VM%!(VAGRANT_COMMA) you can run `vagrant halt` to\nshut it down forcefully%!(VAGRANT_COMMA) or you can run `vagrant suspend` to simply\nsuspend the virtual machine. In either case%!(VAGRANT_COMMA) to restart it again%!(VAGRANT_COMMA)\nsimply run `vagrant up`.
            1424098924,db,provider-name,virtualbox
            1424098924,db,state,not_created
            1424098924,db,state-human-short,not created
            1424098924,db,state-human-long,The environment has not yet been created. Run `vagrant up` to\ncreate the environment. If a machine is not created%!(VAGRANT_COMMA) only the\ndefault provider will be shown. So if a provider is not listed%!(VAGRANT_COMMA)\nthen the machine is not created for that environment.

        Example with VM name:

            $ vagrant status --machine-readable web
            1424099027,web,provider-name,virtualbox
            1424099027,web,state,running
            1424099027,web,state-human-short,running
            1424099027,web,state-human-long,The VM is running. To stop this VM%!(VAGRANT_COMMA) you can run `vagrant halt` to\nshut it down forcefully%!(VAGRANT_COMMA) or you can run `vagrant suspend` to simply\nsuspend the virtual machine. In either case%!(VAGRANT_COMMA) to restart it again%!(VAGRANT_COMMA)\nsimply run `vagrant up`.

        Example with no VM name and single-vm Vagrantfile:

            $ vagrant status --machine-readable
            1424100021,default,provider-name,virtualbox
            1424100021,default,state,not_created
            1424100021,default,state-human-short,not created
            1424100021,default,state-human-long,The environment has not yet been created. Run `vagrant up` to\ncreate the environment. If a machine is not created%!(VAGRANT_COMMA) only the\ndefault provider will be shown. So if a provider is not listed%!(VAGRANT_COMMA)\nthen the machine is not created for that environment.

        Error example with incorrect VM name:

            $ vagrant status --machine-readable api
            1424099042,,error-exit,Vagrant::Errors::MachineNotFound,The machine with the name 'api' was not found configured for\nthis Vagrant environment.

        Error example with missing Vagrantfile:

            $ vagrant status --machine-readable
            1424099094,,error-exit,Vagrant::Errors::NoEnvironmentError,A Vagrant environment or target machine is required to run this\ncommand. Run `vagrant init` to create a new Vagrant environment. Or%!(VAGRANT_COMMA)\nget an ID of a target machine from `vagrant global-status` to run\nthis command on. A final option is to change to a directory with a\nVagrantfile and to try again.
        '''
        # machine-readable output are CSV lines
        output = self._run_vagrant_command(['status', '--machine-readable', vm_name])
        return self._parse_status(output)

    def _parse_status(self, output):
        '''
        Unit testing is so much easier when Vagrant is removed from the
        equation.
        '''
        parsed = self._parse_machine_readable_output(output)
        statuses = []
        # group tuples by target name
        # assuming tuples are sorted by target name, this should group all
        # the tuples with info for each target.
        for target, tuples in itertools.groupby(parsed, lambda tup: tup[1]):
            # transform tuples into a dict mapping "type" to "data"
            info = {kind: data for timestamp, _, kind, data in tuples}
            status = Status(name=target, state=info.get('state'),
                            provider=info.get('provider-name'))
            statuses.append(status)

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
        Run `vagrant box list --machine-readable` and return a list of Box
        objects containing the results.  A Box object has the following
        attributes:

        - name: the box-name.
        - provider: the box-provider.
        - version: the box-version.

        Example output:

            [Box(name='precise32', provider='virtualbox', version='0'),
             Box(name='precise64', provider='virtualbox', version=None),
             Box(name='trusty64', provider='virtualbox', version=None)]

        Implementation Details:

        Example machine-readable box listing output:

            1424141572,,box-name,precise64
            1424141572,,box-provider,virtualbox
            1424141572,,box-version,0
            1424141572,,box-name,python-vagrant-base
            1424141572,,box-provider,virtualbox
            1424141572,,box-version,0

        Note that the box information iterates within the same blank target
        value (the 2nd column).
        '''
        # machine-readable output are CSV lines
        output = self._run_vagrant_command(['box', 'list', '--machine-readable'])
        return self._parse_box_list(output)

    def snapshot_push(self):
        '''
        This takes a snapshot and pushes it onto the snapshot stack.
        '''
        self._call_vagrant_command(['snapshot', 'push'])

    def snapshot_pop(self):
        '''
        This command is the inverse of vagrant snapshot push: it will restore the pushed state.
        '''
        NO_SNAPSHOTS_PUSHED = 'No pushed snapshot found!'
        output = self._run_vagrant_command(['snapshot', 'pop'])
        if NO_SNAPSHOTS_PUSHED in output:
            raise RuntimeError(NO_SNAPSHOTS_PUSHED)

    def snapshot_save(self, name):
        '''
        This command saves a new named snapshot.
        If this command is used, the push and pop subcommands cannot be safely used.
        '''
        self._call_vagrant_command(['snapshot', 'save', name])

    def snapshot_restore(self, name):
        '''
        This command restores the named snapshot.
        '''
        self._call_vagrant_command(['snapshot', 'restore', name])

    def snapshot_list(self):
        '''
        This command will list all the snapshots taken.
        '''
        NO_SNAPSHOTS_TAKEN = 'No snapshots have been taken yet!'
        output = self._run_vagrant_command(['snapshot', 'list'])
        if NO_SNAPSHOTS_TAKEN in output:
            return []
        else:
            return output.splitlines()

    def snapshot_delete(self, name):
        '''
        This command will delete the named snapshot.
        '''
        self._call_vagrant_command(['snapshot', 'delete', name])

    def _parse_box_list(self, output):
        '''
        Remove Vagrant usage for unit testing
        '''
        # Parse box list output
        # Cue snarky comment about how nice it would be if vagrant used JSON
        # or even had a description of the machine readable output for each
        # command

        boxes = []
        # initialize box values
        name = provider = version = None
        for timestamp, target, kind, data in self._parse_machine_readable_output(output):
            if kind == 'box-name':
                # finish the previous box, if any
                if name is not None:
                    boxes.append(Box(name=name, provider=provider, version=version))

                # start a new box
                name = data # box name
                provider = version = None
            elif kind == 'box-provider':
                provider = data
            elif kind == 'box-version':
                version = data

        # finish the previous box, if any
        if name is not None:
            boxes.append(Box(name=name, provider=provider, version=version))

        return boxes

    def box_update(self, name, provider):
        '''
        Updates the box matching name and provider. It is an error if no box
        matches name and provider.
        '''
        self._call_vagrant_command(['box', 'update', name, provider])

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

        Implementation Details:

        Example output of `vagrant plugin list --machine-readable`:

            $ vagrant plugin list --machine-readable
            1424145521,,plugin-name,sahara
            1424145521,sahara,plugin-version,0.0.16
            1424145521,,plugin-name,vagrant-share
            1424145521,vagrant-share,plugin-version,1.1.3%!(VAGRANT_COMMA) system

        Note that the information for each plugin seems grouped within 
        consecutive lines.  That information is also associated sometimes with
        an empty target name and sometimes with the plugin name as the target
        name.  Note also that a plugin version can be like '0.0.16' or 
        '1.1.3, system'.
        '''
        output = self._run_vagrant_command(['plugin', 'list', '--machine-readable'])
        return self._parse_plugin_list(output)

    def _parse_plugin_list(self, output):
        '''
        Remove Vagrant from the equation for unit testing.
        '''
        ENCODED_COMMA = '%!(VAGRANT_COMMA)'

        plugins = []
        # initialize plugin values
        name = None
        version = None
        system = False
        for timestamp, target, kind, data in self._parse_machine_readable_output(output):
            if kind == 'plugin-name':
                # finish the previous plugin, if any
                if name is not None:
                    plugins.append(Plugin(name=name, version=version, system=system))

                # start a new plugin
                name = data # plugin name
                version = None
                system = False
            elif kind == 'plugin-version':
                if ENCODED_COMMA in data:
                    version, etc = data.split(ENCODED_COMMA)
                    system = (etc.strip().lower() == 'system')
                else:
                    version = data
                    system = False

        # finish the previous plugin, if any
        if name is not None:
            plugins.append(Plugin(name=name, version=version, system=system))

        return plugins

    def _parse_machine_readable_output(self, output):
        '''
        param output: a string containing the output of a vagrant command with the `--machine-readable` option.

        returns: a dict mapping each 'target' in the machine readable output to
        a dict.  The dict of each target, maps each target line type/kind to
        its data.

        Machine-readable output is a collection of CSV lines in the format:

           timestamp, target, kind, data

        Target is a VM name, possibly 'default', or ''.  The empty string
        denotes information not specific to a particular VM, such as the
        results of `vagrant box list`.
        '''
        # each line is a tuple of (timestamp, target, type, data)
        # target is the VM name
        # type is the type of data, e.g. 'provider-name', 'box-version'
        # data is a (possibly comma separated) type-specific value, e.g. 'virtualbox', '0'
        parsed_lines = [line.split(',', 4) for line in output.splitlines() if line.strip()]
        # vagrant 1.8 adds additional fields that aren't required,
        # and will break parsing if included in the status lines.
        # filter them out pending future implementation.
        parsed_lines = list(filter(lambda x: x[2] not in ["metadata", "ui", "action"], parsed_lines))
        return parsed_lines

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
        with self.out_cm() as out_fh, self.err_cm() as err_fh:
            subprocess.check_call(command, cwd=self.root, stdout=out_fh,
                                  stderr=err_fh, env=self.env)

    def _run_vagrant_command(self, args):
        '''
        Run a vagrant command and return its stdout.
        args: A sequence of arguments to a vagrant command line.
        e.g. ['up', 'my_vm_name', '--no-provision'] or
        ['up', None, '--no-provision'] for a non-Multi-VM environment.
        '''
        # Make subprocess command
        command = self._make_vagrant_command(args)
        with self.err_cm() as err_fh:
            return compat.decode(subprocess.check_output(command, cwd=self.root,
                                               env=self.env, stderr=err_fh))


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
