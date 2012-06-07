

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


####################
# VAGRANT FUNCTIIONS


class Vagrant(object):
    '''
    Object to up (launch) and destroy (terminate) vagrant virtual machines,
    to check the status of the machine and to report on the configuration
    of the machine.

    Works by using the `vagrant` executable and a `Vagrantfile`.

    Currently does not support specifying `vm-name` arguments in a multi-vm
    environment.
    '''

    # statuses
    RUNNING = 'running' # vagrant up
    NOT_CREATED = 'not created' # vagrant destroy
    POWEROFF = 'poweroff' # vagrant halt

    def __init__(self, root=None):
        '''
        root: a directory containing a file named Vagrantfile.  Defaults to
        os.getcwd(). This is the directory and Vagrantfile that the Vagrant
        instance will operate on.
        '''
        self.root = os.path.abspath(root) if root is not None else os.getcwd()
        self._cached_conf = None

    def up(self):
        '''
        Launch the Vagrant box.
        '''
        subprocess.check_call('vagrant up', shell=True, cwd=self.root)
        self.conf() # cache configuration

    def destroy(self):
        '''
        Terminate the running Vagrant box.
        '''
        subprocess.check_call('vagrant destroy -f', shell=True, cwd=self.root)
        self._cached_conf = None # remove cached configuration

    def status(self):
        '''
        Returns the status of the Vagrant box:
            'not created' if the box is destroyed
            'running' if the box is up
            'poweroff' if the box is halted
            None if no status is found
        There might be other statuses, but the Vagrant docs were unclear.
        '''
        output = subprocess.check_output('vagrant status', shell=True,
                                         cwd=self.root)
        # example output
        '''
        Current VM states:

        default                  poweroff

        The VM is powered off. To restart the VM, simply run `vagrant up`
        '''
        status = None
        for line in output.splitlines():
            if line.startswith('default'):
                status = line.strip().split(None, 1)[1]

        return status

    def conf(self, ssh_config=None):
        '''
        Return a dict containing the keys defined in ssh_config, which
        should include these keys (listed with example values): 'User' (e.g.
        'vagrant'), 'HostName' (e.g. 'localhost'), 'Port' (e.g. '2222'),
        'IdentityFile' (e.g. '/home/todd/.ssh/id_dsa')

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.

        ssh_config: a valid ssh confige file host section.  Defaults to
        the value returned from ssh_config().  For speed, the configuraiton
        parsed from ssh_config is cached for subsequent calls.
        '''
        if self._cached_conf is None or ssh_config is not None:
            conf = self._parse_config(ssh_config)
            self._cached_conf = conf

        return self._cached_conf

    def ssh_config(self):
        '''
        Return the output of 'vagrant ssh-config' which appears to be a valid
        Host section suitable for use in an ssh config file.
        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.

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
        return subprocess.check_output('vagrant ssh-config', shell=True,
                                       cwd=self.root)

    def user(self):
        '''
        Return the ssh user of the vagrant box, e.g. 'vagrant'
        or None if there is no user in the ssh_config.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        return self.conf().get('User')

    def hostname(self):
        '''
        Return the vagrant box hostname, e.g. '127.0.0.1'
        or None if there is no hostname in the ssh_config.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        return self.conf().get('HostName')

    def port(self):
        '''
        Return the vagrant box ssh port, e.g. '2222'
        or None if there is no port in the ssh_config.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        return self.conf().get('Port')

    def keyfile(self):
        '''
        Return the path to the private key used to log in to the vagrant box
        or None if there is no keyfile (IdentityFile) in the ssh_config.
        E.g. '/Users/todd/.vagrant.d/insecure_private_key'

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.

        KeyFile is a synonym for IdentityFile.
        '''
        return self.conf().get('IdentityFile')

    def user_hostname(self):
        '''
        Return a string combining user and hostname, e.g. 'vagrant@127.0.0.1'.
        This string is suitable for use in an ssh commmand.  If user is None
        or empty, it will be left out of the string, e.g. 'localhost'.  If
        hostname is None, have bigger problems.

        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        user = self.user()
        user_prefix = user + '@' if user else ''
        return user_prefix + self.hostname()

    def user_hostname_port(self):
        '''
        Return a string combining user, hostname and port, e.g.
        'vagrant@127.0.0.1:2222'.  This string is suitable for use with Fabric,
        in env.hosts.  If user or port is None or empty, they will be left
        out of the string.  E.g. 'vagrant@localhost', or 'localhost:2222' or
        'localhost'.  If hostname is None, you have bigger problems.


        Raises an Exception if the Vagrant box has not yet been created or
        has been destroyed.
        '''
        user = self.user()
        port = self.port()
        user_prefix = user + '@' if user else ''
        port_suffix = ':' + port if port else ''
        return user_prefix + self.hostname() + port_suffix


    def _parse_config(self, ssh_config=None):
        '''
        This ghetto parser does not parse the full grammar of an ssh config
        file.  It makes assumptions that are (hopefully) correct for the output
        of `vagrant ssh-config`.  Specifically it assumes that there is only
        one Host section, the default vagrant host.  It assumes that every line
        is of the form 'key  value', where key is a single token without any
        whitespace and value is the remaining part of the line.  All leading
        and trailing whitespace is removed from key and value.  For example: 

        '    User vagrant\n'

        Lines with '#' as the first non-whitespace character are considered
        comments and ignored.  Whitespace-only lines are ignored.  This parser
        does NOT handle using an '=' in options.

        See https://github.com/bitprophet/ssh/blob/master/ssh/config.py for a
        more compliant ssh config file parser.
        '''
        if ssh_config is None:
            ssh_config = self.ssh_config()

        # skip blank lines and comment lines
        conf = dict(line.strip().split(None, 1) for line in 
                    ssh_config.splitlines() if line.strip() and 
                    not line.strip().startswith('#'))

        return conf



