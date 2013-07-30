'''
Introduces setup and teardown routines suitable for testing Vagrant.

Note that the tests can take few minutes to run because of the time 
required to bring up/down the VM.

Most test functions (decorated with `@with_setup`) will actually bring the VM
up/down. This for one is the "proper" way of doing things (isolation).  The
downside of such workflow is that it increases the execution time of the test
suite. The other approach (bringing the VM up once and packing all tests
together) is less extensible.  With few tests it may work, but when the test
suite grows it becomes a problem.

In order to mitigate the inconvenience, each test method actually 
encapsulates few related tests. Aside from making the execution time shorter
it also adds to readability.

Before the first test a base box is added to Vagrant under the name 
TEST_BOX_NAME. This box is not deleted after the test suite runs in order 
to avoid downloading of the box file on every run.
'''


import os
import re
import unittest
import shutil
import subprocess
import sys
import tempfile
from nose.tools import eq_, with_setup

import vagrant

# location of a test file on the created box by provisioning in vm_Vagrantfile
TEST_FILE_PATH = '/home/vagrant/python_vagrant_test_file'
# location of Vagrantfiles used for testing.
MULTIVM_VAGRANTFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                   'vagrantfiles', 'multivm_Vagrantfile')
VM_VAGRANTFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                   'vagrantfiles', 'vm_Vagrantfile')
# the names of the vms from the multi-vm Vagrantfile.
VM_1 = 'web'
VM_2 = 'db'
# name of the base box used for testing
TEST_BOX_NAME = "python-vagrant-base"
# url of the box file used for testing
TEST_BOX_URL = "http://files.vagrantup.com/lucid32.box"
# temp dir for testing.
TD = None


def list_boxes():
    '''
    Return a list if tuples containing the box name and box provider of each
    box in `vagrant box list`.
    '''
    # Example `box list` output (vagrant 1.1.5):
    # base                     (virtualbox)
    # precise32                (virtualbox)
    # precise64                (virtualbox)
    # python-vagrant-base      (virtualbox)
    # python-vagrant-dummy-box (virtualbox)
    # Example `box list` output with no boxes (vagrant 1.2.7):
    # There are no installed boxes! Use `vagrant box add` to add some.
    listing = subprocess.check_output('vagrant box list', shell=True)
    boxes = []
    for line in listing.splitlines():
        m = re.search(r'^\s*(?P<name>.+?)\s+\((?P<provider>[^)]+)\)\s*$', line)
        if m:
            print m.groups()
            boxes.append((m.group('name'), m.group('provider')))
    return boxes


def list_box_names():
    '''
    Return a list of the currently installed vagrant box names.
    '''
    return [box[0] for box in list_boxes()]


# MODULE-LEVEL SETUP AND TEARDOWN

def setup():
    '''
    Creates the directory used for testing and sets up the base box if not 
    already set up.

    Creates a directory in a temporary location and checks if there is a base
    box under the `TEST_BOX_NAME`. If not, downloads it from `TEST_BOX_URL` and
    adds to Vagrant.

    This is ran once before the first test (global setup).
    '''
    sys.stderr.write('module setup()\n')
    global TD
    TD = tempfile.mkdtemp()
    sys.stderr.write('test temp dir: {}\n'.format(TD))
    boxes = list_box_names()
    if TEST_BOX_NAME not in boxes:
        cmd = 'vagrant box add {} {}'.format(TEST_BOX_NAME, TEST_BOX_URL)
        subprocess.check_call(cmd, shell=True)


def teardown():
    '''
    Removes the directory created in setup.

    This is run once after the last test.
    '''
    sys.stderr.write('module teardown()\n')
    if TD is not None:
        shutil.rmtree(TD)


# TEST-LEVEL SETUP AND TEARDOWN


def setup_vm():
    shutil.copy(VM_VAGRANTFILE, os.path.join(TD, 'Vagrantfile'))

def teardown_vm():
    '''
    Destroys the VM after each test method.
    It is not an error if the VM has already been destroyed.
    '''
    try:
        subprocess.check_call(
            'vagrant destroy -f'.format(TEST_BOX_NAME), 
            cwd=TD, shell=True)
    except subprocess.CalledProcessError:
        pass
    finally:
        # remove Vagrantfile created by setup 'vagrant init' command.
        os.unlink(os.path.join(TD, "Vagrantfile"))


def setup_multivm():
    shutil.copy(MULTIVM_VAGRANTFILE, os.path.join(TD, 'Vagrantfile'))


def teardown_multivm():
    try:
        # Try to destroy any vagrant box that might be running.
        subprocess.check_call('vagrant destroy -f',
                              cwd=TD, shell=True)
    except subprocess.CalledProcessError:
        pass
    finally:
        # remove Vagrantfile created by setup.
        os.unlink(os.path.join(TD, "Vagrantfile"))



@with_setup(setup_vm, teardown_vm)
def test_vm_status():
    '''
    Test whether vagrant.status() correctly reports state of the VM.
    '''
    v = vagrant.Vagrant(TD)
    assert v.NOT_CREATED in v.status().values(), "Before going up status should be vagrant.NOT_CREATED"
    command = 'vagrant up'
    subprocess.check_call(command, cwd=TD, shell=True)
    assert v.RUNNING in v.status().values(), "After going up status should be vagrant.RUNNING"
    
    command = 'vagrant halt'
    subprocess.check_call(command, cwd=TD, shell=True)
    assert v.POWEROFF in v.status().values(), "After halting status should be vagrant.POWEROFF"

    command = 'vagrant destroy -f'
    subprocess.check_call(command, cwd=TD, shell=True)
    assert v.NOT_CREATED in v.status().values(), "After destroying status should be vagrant.NOT_CREATED"
    

@with_setup(setup_vm, teardown_vm)
def test_vm_lifecycle():
    '''
    Test methods controlling the VM - init(), up(), halt(), destroy().
    '''

    v = vagrant.Vagrant(TD)

    # Test init by removing Vagrantfile, since v.init() will create one.
    os.unlink(os.path.join(TD, 'Vagrantfile'))
    v.init(TEST_BOX_NAME)
    assert v.NOT_CREATED in v.status().values()
        
    v.up()
    assert v.RUNNING in v.status().values()
    
    v.suspend()
    assert v.SAVED in v.status().values()
    
    v.halt()
    assert v.POWEROFF in v.status().values()
    
    v.destroy()
    assert v.NOT_CREATED in v.status().values()


@with_setup(setup_vm, teardown_vm)
def test_vm_config():
    '''
    Test methods retrieving ssh config settings, like user, hostname, and port.
    '''
    v = vagrant.Vagrant(TD)
    v.up()
    command = "vagrant ssh-config"
    ssh_config = subprocess.check_output(command, cwd=TD, shell=True)
    parsed_config = dict(line.strip().split(None, 1) for line in
                            ssh_config.splitlines() if line.strip() and not
                            line.strip().startswith('#'))
    
    user = v.user()
    expected_user = parsed_config["User"] 
    eq_(user, expected_user)
    
    hostname = v.hostname()
    expected_hostname = parsed_config["HostName"]
    eq_(hostname, expected_hostname)
    
    port = v.port()
    expected_port = parsed_config["Port"]
    eq_(port, expected_port)
    
    user_hostname = v.user_hostname()
    eq_(user_hostname, "{}@{}".format(expected_user, expected_hostname))
    
    user_hostname_port = v.user_hostname_port()
    eq_(user_hostname_port,  
        "{}@{}:{}".format(expected_user, expected_hostname, expected_port))
    
    keyfile = v.keyfile()
    eq_(keyfile, parsed_config["IdentityFile"])


@with_setup(setup_vm, teardown_vm)
def test_vm_sandbox_mode():
    '''
    Test methods for enabling/disabling the sandbox mode 
    and committing/rolling back changes.
    
    This depends on the Sahara gem (gem install sahara).
    '''
    command = "vagrant sandbox status"
    try:
        output = subprocess.check_output(command, cwd=TD, shell=True)
    except subprocess.CalledProcessError as e:
        output = e.output
    # output = subprocess.check_output(command, cwd=TD, shell=True)
    sahara_installed = True if not "Usage" in output else False
    eq_(sahara_installed, True, "Sahara gem should be installed")
    
    if sahara_installed:
        v = vagrant.SandboxVagrant(TD)
        
        sandbox_status = v.sandbox_status()
        assert "unknown" in v.status().values(), "Before the VM goes up the status should be 'unknown', " + "got:'{}'".format(sandbox_status)
        
        v.up()
        sandbox_status = v.sandbox_status()
        assert "off" in v.status().values(), "After the VM goes up the status should be 'off', " + "got:'{}'".format(sandbox_status)
        
        v.sandbox_on()
        sandbox_status = v.sandbox_status()
        assert "on" in v.status().values(), "After enabling the sandbox mode the status should be 'on', " + "got:'{}'".format(sandbox_status)
        
        v.sandbox_off()
        sandbox_status = v.sandbox_status()
        assert "off" in v.status().values(), "After disabling the sandbox mode the status should be 'off', " + "got:'{}'".format(sandbox_status)
        
        v.sandbox_on()
        v.halt()
        sandbox_status = v.sandbox_status()
        assert "on" in v.status().values(), "After halting the VM the status should be 'on', " + "got:'{}'".format(sandbox_status)
        
        v.up()
        sandbox_status = v.sandbox_status()
        assert "on" in v.status().values(), "After bringing the VM up again the status should be 'on', " + "got:'{}'".format(sandbox_status)
        
        test_file_contents = _read_test_file(v)
        print test_file_contents
        eq_(test_file_contents, None, "There should be no test file")
        
        _write_test_file(v, "foo")
        test_file_contents = _read_test_file(v)
        print test_file_contents
        eq_(test_file_contents, "foo", "The test file should read 'foo'")
        
        v.sandbox_rollback()            
        test_file_contents = _read_test_file(v)
        print test_file_contents
        eq_(test_file_contents, None, "There should be no test file")
        
        _write_test_file(v, "foo")
        test_file_contents = _read_test_file(v)
        print test_file_contents
        eq_(test_file_contents, "foo", "The test file should read 'foo'")
        v.sandbox_commit()
        _write_test_file(v, "bar")
        test_file_contents = _read_test_file(v)
        print test_file_contents
        eq_(test_file_contents, "bar", "The test file should read 'bar'")
        
        v.sandbox_rollback()            
        test_file_contents = _read_test_file(v)
        print test_file_contents
        eq_(test_file_contents, "foo", "The test file should read 'foo'")
        
        sandbox_status = v._parse_vagrant_sandbox_status("Usage: ...")
        eq_(sandbox_status, "not installed", "When 'vagrant sandbox status'" +
            " outputs vagrant help status should be 'not installed', " +
            "got:'{}'".format(sandbox_status))
        
        v.destroy()
        sandbox_status = v.sandbox_status()
        assert "unknown" in v.status().values(), "After destroying the VM the status should be 'unknown', " + "got:'{}'".format(sandbox_status)

        
@with_setup(setup_vm, teardown_vm)
def test_boxes():
    '''
    Test methods for manipulating boxes - adding, listing, removing.
    '''
    v = vagrant.Vagrant(TD)
    box_name = "python-vagrant-dummy-box"
    provider = "virtualbox"

    # Start fresh with no dummy box
    boxes = list_boxes()
    if (box_name, provider) in boxes:
        subprocess.check_call(
            'vagrant box remove {} {}'.format(box_name, provider), shell=True)

    # Test that there is no dummy box
    boxes = list_boxes()
    eq_((box_name, provider) in boxes, False,
        "There should be no dummy box before it's added")

    # Test adding a box
    v.box_add(box_name, TEST_BOX_URL)
    boxes = list_boxes()
    eq_((box_name, provider) in boxes, True,
        "There should be a dummy box in the list of boxes")

    # Test listing box names
    box_names = list_box_names()
    reported_box_names = v.box_list()
    for box in box_names:
        eq_(box in reported_box_names, True,
            "The box '{}' should be in the list returned by box_list()".format(box))

    # Test listing box names and providers
    boxes = list_boxes()
    reported_boxes = v.box_list_long()
    for box in boxes:
        eq_(box in reported_boxes, True,
            "The box '{}' should be in the list returned by box_list()".format(box))

    # Test removing a box with name and provider
    v.box_remove(box_name, provider)
    boxes = list_boxes()
    eq_((box_name, provider) in boxes, False,
        "There should be no dummy box after it's been deleted")


@with_setup(setup_vm, teardown_vm)
def test_provisioning():
    '''
    Test provisioning support.  The tested provision config creates a file on
    the vm with the contents 'foo'.
    '''
    v = vagrant.Vagrant(TD)
    
    v.up(no_provision=True)
    test_file_contents = _read_test_file(v)
    eq_(test_file_contents, None, "There should be no test file after up()")
    
    v.provision()
    test_file_contents = _read_test_file(v)
    print "Contents: {}".format(test_file_contents)
    eq_(test_file_contents, "foo", "The test file should contain 'foo'")


@with_setup(setup_multivm, teardown_multivm)
def test_multivm_lifecycle():
    v = vagrant.Vagrant(TD)

    # test getting multiple statuses at once
    statuses = v.status()
    eq_(statuses[VM_1], v.NOT_CREATED)
    eq_(statuses[VM_2], v.NOT_CREATED)

    v.up(vm_name=VM_1)
    eq_(v.status()[VM_1], v.RUNNING)
    eq_(v.status()[VM_2], v.NOT_CREATED)

    # start both vms
    v.up()
    eq_(v.status()[VM_1], v.RUNNING)
    eq_(v.status()[VM_2], v.RUNNING)

    v.halt(vm_name=VM_1)
    eq_(v.status()[VM_1], v.POWEROFF)
    eq_(v.status()[VM_2], v.RUNNING)

    v.destroy(vm_name=VM_1)
    eq_(v.status()[VM_1], v.NOT_CREATED)
    eq_(v.status()[VM_2], v.RUNNING)

    v.suspend(vm_name=VM_2)
    eq_(v.status()[VM_1], v.NOT_CREATED)
    eq_(v.status()[VM_2], v.SAVED)

    v.destroy(vm_name=VM_2)
    eq_(v.status()[VM_1], v.NOT_CREATED)
    eq_(v.status()[VM_2], v.NOT_CREATED)


@with_setup(setup_multivm, teardown_multivm)
def test_multivm_config():
    '''
    Test methods retrieving configuration settings.
    '''
    v = vagrant.Vagrant(TD)
    v.up(vm_name=VM_1)
    command = "vagrant ssh-config " + VM_1
    ssh_config = subprocess.check_output(command, cwd=TD, shell=True)
    parsed_config = dict(line.strip().split(None, 1) for line in
                            ssh_config.splitlines() if line.strip() and not
                            line.strip().startswith('#'))

    user = v.user(vm_name=VM_1)
    expected_user = parsed_config["User"] 
    eq_(user, expected_user)

    hostname = v.hostname(vm_name=VM_1)
    expected_hostname = parsed_config["HostName"]
    eq_(hostname, expected_hostname)

    port = v.port(vm_name=VM_1)
    expected_port = parsed_config["Port"]
    eq_(port, expected_port)

    user_hostname = v.user_hostname(vm_name=VM_1)
    eq_(user_hostname, "{}@{}".format(expected_user, expected_hostname))

    user_hostname_port = v.user_hostname_port(vm_name=VM_1)
    eq_(user_hostname_port,
        "{}@{}:{}".format(expected_user, expected_hostname, expected_port))

    keyfile = v.keyfile(vm_name=VM_1)
    eq_(keyfile, parsed_config["IdentityFile"])


def _execute_command_in_vm(v, command):
    '''
    Run command via ssh on the test vagrant box.  Returns a tuple of the
    return code and output of the command.
    '''
    # ignore the fact that this host is not in our known hosts
    ssh_command = [vagrant.VAGRANT_EXE, 'ssh', '-c', command]
    return subprocess.check_output(ssh_command, cwd=v.root)


def _write_test_file(v, file_contents):
    '''
    Writes given contents to the test file.
    '''
    command = "echo '{}' > {}".format(file_contents, TEST_FILE_PATH)
    _execute_command_in_vm(v, command)


def _read_test_file(v):
    '''
    Returns the contents of the test file stored in the VM or None if there
    is no file.
    '''
    command = 'cat {}'.format(TEST_FILE_PATH)
    try:
        output = _execute_command_in_vm(v, command)
        return output.strip()
    except subprocess.CalledProcessError:
        return None


