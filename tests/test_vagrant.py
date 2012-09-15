import os
import unittest
import shutil
import subprocess
import sys
import tempfile
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
    
    def test_status(self):
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
        Test methods controlling the VM - up(), destory().
        '''
        v = vagrant.Vagrant(self.td)
        eq_(v.status(), v.NOT_CREATED)
        v.up()
        eq_(v.status(), v.RUNNING)
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
