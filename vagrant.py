'''
Python bindings for working with Vagrant and Vagrantfiles.  Do useful things
with the `vagrant` CLI without the boilerplate (and errors) of calling
`vagrant` and parsing the results.

Quick and dirty test to up, look at, and destroy (!) a Vagrant box.  Run from
the directory holding your Vagrantfile.

python -c 'import vagrant
v = vagrant.Vagrant()
v.up()
print v.status()
print v.user()
print v.hostname()
print v.port()
print v.keyfile()
print v.user_hostname()
print v.user_hostname_port()
print v.conf()
v.destroy();
'

For unit tests, see tests/test_vagrant.py

Dependencies:

- `vagrant` should be installed and in your PATH.

'''

import os
import subprocess
import sys


def which(program):
    '''
    Emulate unix 'which' command.
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python/377028#377028
    '''
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


# The full path to the vagrant executable, e.g. '/usr/bin/vagrant'
VAGRANT_EXE = which('vagrant')


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

    BASE_BOXES = {
        'ubuntu-Lucid32': 'http://files.vagrantup.com/lucid32.box',
        'ubuntu-lucid32': 'http://files.vagrantup.com/lucid32.box',
        'ubuntu-lucid64': 'http://files.vagrantup.com/lucid64.box',
        'ubuntu-precise32': 'http://files.vagrantup.com/precise32.box',
        'ubuntu-precise64': 'http://files.vagrantup.com/precise64.box',
    }

    def __init__(self, root=None):
        '''
        root: a directory containing a file named Vagrantfile.  Defaults to
        os.getcwd(). This is the directory and Vagrantfile that the Vagrant
        instance will operate on.
        '''
        self.root = os.path.abspath(root) if root is not None else os.getcwd()
        self._cached_conf = {}

    def init(self, box_name, box_path=None):
        '''
        Init the VM.
        '''
        print "Checking for " + box_name
        if box_name not in self.box_list():
            if self._confirm(box_name + " not installed. Add box?"):
                if box_path is None:
                    try:
                        box_path = self.BASE_BOXES[box_name]
                    except KeyError:
                        print "Box not found in url list. Please specify the box path/url."
                        sys.exit(1)
                self.box_add(box_name, box_path)
            else:
                sys.exit(1)
        self._run_vagrant_command('init', box_name)

    def up(self, no_provision=False, vm_name=None):
        '''
        Launch the Vagrant box.
        '''
        no_provision_arg = '--no-provision' if no_provision else None
        self._run_vagrant_command('up', vm_name, no_provision_arg)
        try:
            self.conf(vm_name=vm_name)  # cache configuration
        except subprocess.CalledProcessError as e:
            # in multi-VM environments, up() can be used to start all VMs,
            # however vm_name is required for conf() or ssh_config().
            pass

    def halt(self, vm_name=None):
        '''
        Halt the Vagrant box.
        '''
        self._run_vagrant_command('halt', vm_name)
        self._cached_conf[vm_name] = None  # remove cached configuration

    def destroy(self, vm_name=None):
        '''
        Terminate the running Vagrant box.
        '''
        self._run_vagrant_command('destroy', vm_name, '-f')
        self._cached_conf[vm_name] = None  # remove cached configuration

    def status(self, vm_name=None):
        '''
        Returns the status of a Vagrant box or a dictionary mapping vm names
        to statuses.
        
        In a single-VM environment or when the vm_name parameter is used in
        a multi-VM environment, a status string is returned:

        - 'not created' if the box is destroyed
        - 'running' if the box is up
        - 'poweroff' if the box is halted
        - None if no status is found

        There might be other statuses, but the Vagrant docs were unclear.

        When vm_name is not given in a multi-VM environment a dictionary
        mapping vm names to statuses will be returned.
        '''
        # example output:
        # Current VM states:
        #
        # default                  poweroff
        #
        # The VM is powered off. To restart the VM, simply run `vagrant up`

        # example multi-VM environment output:
        # Current VM states:
        #
        # web                      running
        # db                       running
        #
        # This environment represents multiple VMs. The VMs are all listed
        # above with their current state. For more information about a specific
        # VM, run `vagrant status NAME`.

        output = self._run_vagrant_command('status', vm_name)
        # sys.stderr.write('status {}: {}\n'.format(vm_name, output))
        statuses = {}
        state = 1 # parsing state variable.
        # The format of output is expected to be a "Current VM states:" line
        # followed by a blank line, followed by one or more status lines,
        # followed by a blank line.
        for line in output.splitlines():
            if state == 1 and line.strip().startswith('Current VM states:'):
                state = 2
            elif state == 2 and not line.strip():
                state = 3
            elif state == 3 and line.strip():
                this_vm_name, status = line.strip().split(None, 1)
                statuses[this_vm_name] = status
            elif state == 3 and not line.strip():
                break

        if len(statuses) == 0:
            # no status found
            return None
        elif len(statuses) == 1:
            # single-VM environment or multi-VM env and vm_name arg given.
            return statuses.values()[0]
        else:
            # multi-VM environment
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
        return self._run_vagrant_command('ssh-config', vm_name)

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

    def box_add(self, box_name, box_url):
        '''
        Adds a box with given name, from given url.
        '''
        self._run_vagrant_command('box', 'add', box_name, box_url)

    def box_list(self):
        '''
        Returns a list of all available box names.
        '''
        output = self._run_vagrant_command('box', 'list')
        return [line.strip() for line in output.splitlines()]

    def box_remove(self, box_name):
        '''
        Removes the box with given name.
        '''
        self._run_vagrant_command('box', 'remove', box_name)

    def provision(self, vm_name=None):
        '''
        Runs the provisioners defined in the Vagrantfile.
        '''
        self._run_vagrant_command('provision', vm_name)

    def _parse_config(self, ssh_config):
        '''
        This ghetto parser does not parse the full grammar of an ssh config
        file.  It makes assumptions that are (hopefully) correct for the output
        of `vagrant ssh-config [vm-name]`.  Specifically it assumes that there
        is only one Host section, the default vagrant host.  It assumes that
        every line is of the form 'key  value', where key is a single token
        without any whitespace and value is the remaining part of the line.
        All leading and trailing whitespace is removed from key and value.  For
        example:

        '    User vagrant\n'

        Lines with '#' as the first non-whitespace character are considered
        comments and ignored.  Whitespace-only lines are ignored.  This parser
        does NOT handle using an '=' in options.

        See https://github.com/bitprophet/ssh/blob/master/ssh/config.py for a
        more compliant ssh config file parser.
        '''
        # skip blank lines and comment lines
        conf = dict(line.strip().split(None, 1) for line in
                    ssh_config.splitlines() if line.strip() and
                    not line.strip().startswith('#'))
        return conf

    def _run_vagrant_command(self, *args):
        '''
        args: A tuple of arguments to a vagrant command line.
        e.g. ['up', 'my_vm_name', '--no-provision'] or
        ['up', None, '--no-provision'] for a non-Multi-VM environment.
        '''
        # filter out None args.  Since vm_name is None in non-Multi-VM
        # environments, this quitely removes it from the arguments list
        # when it is not specified.
        command = ['vagrant'] + [arg for arg in args if arg is not None]
        return subprocess.check_output(command, cwd=self.root)

    def _confirm(self, prompt=None, resp=False):
        '''
        Prompts for yes or no response from the user. Returns True for yes
        and False for no.

        :prompt resp: The default value assumed by the caller when
        user simply types ENTER.

        >>> confirm(prompt='Create Directory?', resp=True)
        Create Directory? [Y/n]:
        True
        >>> confirm(prompt='Create Directory?', resp=False)
        Create Directory? [y/N]:
        False
        >>> confirm(prompt='Create Directory?', resp=False)
        Create Directory? [y/N]: y
        True

        '''

        if prompt is None:
            prompt = 'Confirm'

        if resp:
            prompt = '%s [%s/%s]: ' % (prompt, 'Y', 'n')
        else:
            prompt = '%s [%s/%s]: ' % (prompt, 'y', 'N')

        while True:
            ans = raw_input(prompt)
            if not ans:
                return resp
            if ans not in ['y', 'Y', 'n', 'N']:
                print 'Please enter y or n.'
                continue
            if ans == 'y' or ans == 'Y':
                return True
            if ans == 'n' or ans == 'N':
                return False


class SandboxVagrant(Vagrant):
    '''
    Support for sandbox mode using the Sahara gem (https://github.com/jedi4ever/sahara).
    '''

    def _run_sandbox_command(self, *args):
        return self._run_vagrant_command('sandbox', *args)

    def sandbox_commit(self, vm_name=None):
        '''
        Permanently writes all the changes made to the VM.
        '''
        self._run_sandbox_command('commit', vm_name)

    def sandbox_off(self, vm_name=None):
        '''
        Disables the sandbox mode.
        '''
        self._run_sandbox_command('off', vm_name)

    def sandbox_on(self, vm_name=None):
        '''
        Enables the sandbox mode.

        This requires the Sahara gem to be installed
        (https://github.com/jedi4ever/sahara).
        '''
        self._run_sandbox_command('on', vm_name)

    def sandbox_rollback(self, vm_name=None):
        '''
        Reverts all the changes made to the VM since the last commit.
        '''
        self._run_sandbox_command('rollback', vm_name)

    def sandbox_status(self, vm_name=None):
        '''
        Returns the status of the sandbox mode.

        Possible values are:
        - on
        - off
        - unknown
        - not installed
        '''
        vagrant_sandbox_output = self._run_sandbox_command('status', vm_name)
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

