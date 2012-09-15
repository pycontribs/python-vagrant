import os
import unittest
import shutil
import subprocess
import sys
import tempfile
from fabric.api import env, execute, task, run
from fabric.state import connections
from nose.tools import eq_

import vagrant

class VagrantTest(unittest.TestCase):
    '''
    Introduces setup and teardown routines suitable for testing Vagrant.
    
    Note that the tests can take few minutes to run because of the time 
    required to bring up/down the VM.
    
    Each test method (test_foo()) will actually bring the VM up/down. This
    for one is the "proper" way of doing things (isolation). 
    The downside of such workflow is that it increases the execution time 
    of the test suite. The other approach (bringing the VM up once and packing 
    all tests together) proved inextensible however. 
    With few tests it may work, but when the test suite grows it becomes 
    a problem.
    
    In order to mitigate the inconvenience, each test method actually 
    encapsulates few related tests. Aside from making the execution time shorter
    it also adds to readability.
    
    Before the first test a base box is added to Vagrant under the name 
    TEST_BOX_NAME. This box is not deleted after the test suite runs in order 
    to avoid multiple downloads of the same box file on every run.
    ''' 

    # name of the base box used for testing
    TEST_BOX_NAME = "python-vagrant-base"
    
    # url of the box file used for testing
    TEST_BOX_URL = "http://files.vagrantup.com/lucid32.box"
    
    @classmethod
    def setupAll(cls):
        '''
        Creates the directory used for testing and sets up the base box if not 
        already set up.
        
        Creates a directory in a temporary location and checks if there is 
        a base box under the `TEST_BOX_NAME`. If not, downloads it from 
        `TEST_BOX_URL` and adds to Vagrant.
         
        This is ran once before the first test (global setup).
        '''
        cls.td = tempfile.mkdtemp()
        boxes = subprocess.check_output(
            'vagrant box list', cwd=cls.td, shell=True)
        
        if cls.TEST_BOX_NAME not in \
            [line.strip() for line in boxes.splitlines()]:
            add_command = ('vagrant box add {} {}'.format(
                cls.TEST_BOX_NAME,cls.TEST_BOX_URL))
            subprocess.check_call(add_command, cwd=cls.td, shell=True)
    
    @classmethod
    def teardownAll(cls):
        '''
        Removes the directory created in `meth:setupAll`.
        
        This is ran once after the last test.
        '''
        shutil.rmtree(cls.td)
        
    def setUp(self):
        '''
        Initializes the VM before each test method (test_foo()).
        '''
        subprocess.check_call(
            'vagrant init "{}"'.format(self.TEST_BOX_NAME), 
            cwd=self.td, shell=True)
    
    def tearDown(self):
        '''
        Destroys the VM after each test method finishes.
        
        It is not an error if the VM has already been destroyed.
        '''
        try:
            subprocess.check_call(
                'vagrant destroy -f'.format(self.TEST_BOX_NAME), 
                cwd=self.td, shell=True)
            os.unlink( os.path.join(self.td,"Vagrantfile"))
        except subprocess.CalledProcessError:
            pass
    
    def test_vm_status(self):
        '''
        Test whether vagrant.status() correctly reports state of the VM.
        '''
        v = vagrant.Vagrant(self.td)
        eq_(v.status(), v.NOT_CREATED, 
            "Before going up status should be vagrant.NOT_CREATED")
        command = 'vagrant up'
        subprocess.check_call(command, cwd=self.td, shell=True)
        eq_(v.status(), v.RUNNING, 
            "After going up status should be vagrant.RUNNING")
        
        command = 'vagrant halt'
        subprocess.check_call(command, cwd=self.td, shell=True)
        eq_(v.status(), v.POWEROFF, 
            "After halting status should be vagrant.POWEROFF")
    
        command = 'vagrant destroy -f'
        subprocess.check_call(command, cwd=self.td, shell=True)
        eq_(v.status(), v.NOT_CREATED, 
            "After destroying status should be vagrant.NOT_CREATED")
        
    def test_vm_lifecycle(self):
        '''
        Test methods controlling the VM - up(), destroy().
        '''
        v = vagrant.Vagrant(self.td)
        eq_(v.status(), v.NOT_CREATED)
            
        v.up()
        eq_(v.status(), v.RUNNING)
        
        v.halt()
        eq_(v.status(), v.POWEROFF)
        
        v.destroy()
        eq_(v.status(), v.NOT_CREATED)
        
    def test_vm_config(self):
        '''
        Test methods retrieving configuration settings.
        '''
        v = vagrant.Vagrant(self.td)
        v.up()
        command = "vagrant ssh-config"
        ssh_config = subprocess.check_output(command, cwd=self.td, shell=True)
        parsed_config = dict(
            line.strip().split(None, 1) for line in 
                ssh_config.splitlines() if line.strip() and not \
                    line.strip().startswith('#'))
        
        user = v.user()
        expected_user = parsed_config[ "User" ] 
        eq_(user, expected_user)
        
        hostname = v.hostname()
        expected_hostname = parsed_config[ "HostName" ] 
        eq_(hostname, expected_hostname)
        
        port = v.port()
        expected_port = parsed_config[ "Port" ] 
        eq_(port, expected_port)
        
        user_hostname = v.user_hostname()
        eq_(user_hostname, "{}@{}".format(expected_user, expected_hostname))
        
        user_hostname_port = v.user_hostname_port()
        eq_(user_hostname_port,  
            "{}@{}:{}".format(expected_user, expected_hostname, expected_port))
        
        keyfile = v.keyfile()
        eq_(keyfile, parsed_config[ "IdentityFile" ])

    def test_vm_sandbox_mode(self):
        '''
        Test methods for enabling/disabling the sandbox mode 
        and committing/rolling back changes.
        
        This depends on the Sahara gem (gem install sahara).
        '''
        command = "vagrant sandbox status"
        output = subprocess.check_output(
                command, cwd=self.td, shell=True)
        sahara_installed = True if not "Usage" in output else False
        eq_(sahara_installed, True, "Sahara gem should be installed")
        
        if sahara_installed:
            v = vagrant.Vagrant(self.td)
            
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "unknown", 
                "Before the VM goes up the status should be 'unknown', " +
                "got:'{}'".format( sandbox_status ) )
            
            v.up()
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "off", 
                "After the VM goes up the status should be 'off', " +
                "got:'{}'".format( sandbox_status ) )
            
            v.sandbox_enable()
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "on", 
                "After enabling the sandbox mode the status should be 'on', " +
                "got:'{}'".format( sandbox_status ) )
            
            v.sandbox_disable()
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "off", 
                "After disabling the sandbox mode the status should be 'off', " +
                "got:'{}'".format( sandbox_status ) )
            
            v.sandbox_enable()
            v.halt()
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "on", 
                "After halting the VM the status should be 'on', " +
                "got:'{}'".format( sandbox_status ) )
            
            v.up()
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "on", 
                "After bringing the VM up again the status should be 'on', " +
                "got:'{}'".format( sandbox_status ) )
            
            test_file_contents = self._test_file_contents()
            eq_( test_file_contents, None, "There should be no test file" )
            
            self._write_test_file( "foo" )
            test_file_contents = self._test_file_contents()
            eq_( test_file_contents, "foo", "The test file should read 'foo'" )
            
            self._close_fabric_connections()
            v.sandbox_rollback()            
            test_file_contents = self._test_file_contents()
            eq_( test_file_contents, None, "There should be no test file" )
            
            self._write_test_file( "foo" )
            test_file_contents = self._test_file_contents()
            eq_( test_file_contents, "foo", "The test file should read 'foo'" )
            self._close_fabric_connections()
            v.sandbox_commit()
            self._write_test_file( "bar" )
            test_file_contents = self._test_file_contents()
            eq_( test_file_contents, "bar", "The test file should read 'bar'" )
            self._close_fabric_connections()
            v.sandbox_rollback()
            
            test_file_contents = self._test_file_contents()
            eq_( test_file_contents, "foo", "The test file should read 'foo'" )
            
            v.destroy()
            sandbox_status = v.sandbox_status()
            eq_(sandbox_status, "unknown", 
                "After destroying the VM the status should be 'unknown', " +
                "got:'{}'".format( sandbox_status ) )
            
            sandbox_status = v._parse_vagrant_sandbox_status( "Usage: ..." )
            eq_(sandbox_status, "not installed", "When 'vagrant sandbox status'" +
                " outputs vagrant help status should be 'not installed', " +
                "got:'{}'".format( sandbox_status ) )

    def _close_fabric_connections(self):
        '''
        Closes all fabric connections to avoids "inactive" ssh connection errors.
        '''
        for key in connections.keys():
            connections[key].close()
            del connections[key]

    def _execute_task_in_vm(self, task, *args, **kwargs):
        '''
        Executes the task on the VM and returns the output.
        '''
        v = vagrant.Vagrant(self.td)
        env.hosts = [v.user_hostname_port()]
        env.key_filename = v.keyfile()
        env.warn_only = True
        env.disable_known_hosts = True #useful for when the vagrant box ip changes.
        return execute(task, *args, **kwargs)
    
    def _write_test_file(self, file_contents):
        '''
        Writes given contents to the test file.
        '''
        @task
        def write_file_contents(file_contents):
            return run('echo "{}" > ~/python_vagrant_test_file'.format(
                file_contents))
        contents = self._execute_task_in_vm(write_file_contents, file_contents)
    
    def _test_file_contents(self):
        '''
        Returns the contents of the test file stored in the VM or None if there
        is no file.
        '''    
        @task
        def read_file_contents():
            return run('cat ~/python_vagrant_test_file')
        
        contents = self._execute_task_in_vm(read_file_contents).values()[ 0 ]
        if "No such file or directory" in contents:
            contents = None
        return contents
        