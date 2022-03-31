"""
Introduces setup and teardown routines suitable for testing Vagrant.

Note that the tests can take few minutes to run because of the time
required to bring up/down the VM.

Most test functions using `vm` fixture will actually bring the VM
up/down. This is the "proper" way of doing things (isolation).  However, the
downside of such a workflow is that it increases the execution time of the test
suite.

Before the first test a base box is added to Vagrant under the name
TEST_BOX_NAME. This box is not deleted after the test suite runs in order
to avoid downloading of the box file on every run.
"""

from __future__ import print_function
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Generator


import pytest
from _pytest.fixtures import FixtureRequest

import vagrant
from vagrant import compat


# must be defined before TEST_PROVIDER.
def get_provider() -> str:
    """
    Return the provider to use for testing and allow to set it
    with PYTHON_VAGRANT_TEST_PROVIDER environment variable is set.
    Defauts to virtualbox
    """
    my_prov = "virtualbox"
    if "PYTHON_VAGRANT_TEST_PROVIDER" in os.environ:
        my_prov = os.environ["PYTHON_VAGRANT_TEST_PROVIDER"]
    return my_prov


# location of Vagrant executable
VAGRANT_EXE = vagrant.get_vagrant_executable()

# location of a test file on the created box by provisioning in vm_Vagrantfile
TEST_FILE_PATH = "/home/vagrant/python_vagrant_test_file"
# location of Vagrantfiles used for testing.
MULTIVM_VAGRANTFILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vagrantfiles", "multivm_Vagrantfile"
)
VM_VAGRANTFILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vagrantfiles", "vm_Vagrantfile"
)
SHELL_PROVISION_VAGRANTFILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "vagrantfiles",
    "shell_provision_Vagrantfile",
)
# the names of the vms from the multi-vm Vagrantfile.
VM_1 = "web"
VM_2 = "db"
# name of the base box used for testing
TEST_BOX_URL = "generic/alpine315"
TEST_BOX_NAME = TEST_BOX_URL
TEST_PROVIDER = get_provider()
TEST_DUMMY_BOX_URL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tools", f"dummy-{TEST_PROVIDER}.box"
)


@pytest.fixture(name="test_dir", scope="session")
def fixture_test_dir() -> Generator[str, None, None]:
    """
    Creates the directory used for testing and sets up the base box if not
    already set up.

    Creates a directory in a temporary location and checks if there is a base
    box under the `TEST_BOX_NAME`. If needed it downloads it.

    This is ran once before the first test (global setup).
    """
    sys.stderr.write("module setup()\n")
    my_dir = tempfile.mkdtemp()
    sys.stderr.write("test temp dir: {}\n".format(my_dir))
    boxes = list_box_names()
    if TEST_BOX_NAME not in boxes:
        cmd = [VAGRANT_EXE, "box", "add", "--provider", TEST_PROVIDER, TEST_BOX_URL]
        subprocess.check_call(cmd)

    yield my_dir
    # Removes the directory created initially, runs once after the last test
    sys.stderr.write("module teardown()\n")
    if my_dir is not None:
        try:
            cmd = [VAGRANT_EXE, "destroy", "-f"]
            subprocess.check_call(cmd, cwd=my_dir)
        except subprocess.CalledProcessError:
            pass

        shutil.rmtree(my_dir)


def list_box_names():
    """
    Return a list of the currently installed vagrant box names.  This is
    implemented outside of `vagrant.Vagrant`, so that it will still work
    even if the `Vagrant.box_list()` implementation is broken.
    """
    listing = compat.decode(
        subprocess.check_output([VAGRANT_EXE, "box", "list", "--machine-readable"])
    )
    box_names = []
    for line in listing.splitlines():
        # Vagrant 1.8 added additional fields to the --machine-readable output,
        # so unpack the fields according to the number of separators found.
        if line.count(",") == 3:
            timestamp, _, kind, data = line.split(",")
        else:
            timestamp, _, kind, data, extra_data = line.split(",")
        if kind == "box-name":
            box_names.append(data.strip())
    return box_names


# TEST-LEVEL SETUP AND TEARDOWN


@pytest.fixture(name="vm_dir", scope="module")
def fixture_vm_dir(request: FixtureRequest, test_dir) -> Generator[str, None, None]:
    """
    Make and return a function that sets up the temporary directory with a
    Vagrantfile.  By default, use VM_VAGRANTFILE.
    vagrantfile: path to a vagrantfile to use as Vagrantfile in the testing temporary directory.
    """
    vagrantfile = getattr(request, "param", VM_VAGRANTFILE)

    shutil.copy(vagrantfile, os.path.join(test_dir, "Vagrantfile"))
    yield test_dir
    # teardown: Attempts to destroy every VM in the Vagrantfile in the temporary directory.
    # It is not an error if a VM has already been destroyed.
    try:
        # Try to destroy any vagrant box that might be running.
        subprocess.check_call([VAGRANT_EXE, "destroy", "-f"], cwd=test_dir)
    except subprocess.CalledProcessError:
        pass
    finally:
        # remove Vagrantfile created by setup.
        os.unlink(os.path.join(test_dir, "Vagrantfile"))


def test_parse_plugin_list(vm_dir):
    """
    Test the parsing the output of the `vagrant plugin list` command.
    """
    # listing should match output generated by `vagrant plugin list`.
    listing = """1424145521,,plugin-name,sahara
1424145521,sahara,plugin-version,0.0.16
1424145521,,plugin-name,vagrant-share
1424145521,vagrant-share,plugin-version,1.1.3%!(VAGRANT_COMMA) system
"""
    # Can compare tuples to Plugin class b/c Plugin is a collections.namedtuple.
    goal = [("sahara", "0.0.16", False), ("vagrant-share", "1.1.3", True)]
    v = vagrant.Vagrant(vm_dir)
    parsed = v._parse_plugin_list(listing)
    assert (
        goal == parsed
    ), "The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}".format(
        listing, goal, parsed
    )


def test_parse_box_list(vm_dir):
    """
    Test the parsing the output of the `vagrant box list` command.
    """
    listing = """ 1424141572,,box-provider,virtualbox
1424141572,,box-version,0
1424141572,,box-name,generic/alpine315
1424141572,,box-provider,virtualbox
1424141572,,box-version,0
"""
    # Can compare tuples to Box class b/c Box is a collections.namedtuple.
    goal = [
        (TEST_BOX_NAME, "virtualbox", "0"),
    ]
    v = vagrant.Vagrant(vm_dir)
    parsed = v._parse_box_list(listing)
    assert (
        goal == parsed
    ), "The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}".format(
        listing, goal, parsed
    )


def test_parse_status(vm_dir):
    """
    Test the parsing the output of the `vagrant status` command.
    """
    listing = """1424098924,web,provider-name,virtualbox
1424098924,web,state,running
1424098924,web,state-human-short,running
1424098924,web,state-human-long,The VM is running. To stop this VM%!(VAGRANT_COMMA) you can run `vagrant halt` to\\nshut it down forcefully%!(VAGRANT_COMMA) or you can run `vagrant suspend` to simply\\nsuspend the virtual machine. In either case%!(VAGRANT_COMMA) to restart it again%!(VAGRANT_COMMA)\\nsimply run `vagrant up`.
1424098924,db,provider-name,virtualbox
1424098924,db,state,not_created
1424098924,db,state-human-short,not created
1424098924,db,state-human-long,The environment has not yet been created. Run `vagrant up` to\\ncreate the environment. If a machine is not created%!(VAGRANT_COMMA) only the\\ndefault provider will be shown. So if a provider is not listed%!(VAGRANT_COMMA)\\nthen the machine is not created for that environment.
"""
    # Can compare tuples to Status class b/c Status is a collections.namedtuple.
    goal = [("web", "running", "virtualbox"), ("db", "not_created", "virtualbox")]
    v = vagrant.Vagrant(vm_dir)
    parsed = v._parse_status(listing)
    assert (
        goal == parsed
    ), "The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}".format(
        listing, goal, parsed
    )


def test_parse_aws_status(vm_dir):
    """
    Test the parsing the output of the `vagrant status` command for an aws instance.
    """
    listing = """1462351212,default,action,read_state,start
1462351214,default,action,read_state,end
1462351214,default,metadata,provider,aws
1462351214,default,action,read_state,start
1462351215,default,action,read_state,end
1462351215,default,action,read_state,start
1462351216,default,action,read_state,end
1462351216,default,action,read_state,start
1462351217,default,action,read_state,end
1462351217,default,provider-name,aws
1462351217,default,state,running
1462351217,default,state-human-short,running
1462351217,default,state-human-long,The EC2 instance is running. To stop this machine%!(VAGRANT_COMMA) you can run\\n`vagrant halt`. To destroy the machine%!(VAGRANT_COMMA) you can run `vagrant destroy`.
1462351217,default,action,read_state,start
1462351219,default,action,read_state,end
1462351219,,ui,info,Current machine states:\\n\\ndefault (aws)\\n\\nThe EC2 instance is running. To stop this machine%!(VAGRANT_COMMA) you can run\\n`vagrant halt`. To destroy the machine%!(VAGRANT_COMMA) you can run `vagrant destroy`.
"""
    # Can compare tuples to Status class b/c Status is a collections.namedtuple.
    goal = [("default", "running", "aws")]
    v = vagrant.Vagrant(vm_dir)
    parsed = v._parse_status(listing)
    assert (
        goal == parsed
    ), "The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}".format(
        listing, goal, parsed
    )


def test_vm_status(vm_dir):
    """
    Test whether vagrant.status() correctly reports state of the VM, in a
    single-VM environment.
    """
    v = vagrant.Vagrant(vm_dir)
    assert (
        v.NOT_CREATED == v.status()[0].state
    ), "Before going up status should be vagrant.NOT_CREATED"
    command = [VAGRANT_EXE, "up"]
    subprocess.check_call(command, cwd=vm_dir)
    assert (
        v.RUNNING in v.status()[0].state
    ), "After going up status should be vagrant.RUNNING"

    command = [VAGRANT_EXE, "halt"]
    subprocess.check_call(command, cwd=vm_dir)
    assert (
        v.POWEROFF in v.status()[0].state
    ), "After halting status should be vagrant.POWEROFF"

    command = [VAGRANT_EXE, "destroy", "-f"]
    subprocess.check_call(command, cwd=vm_dir)
    assert (
        v.NOT_CREATED in v.status()[0].state
    ), "After destroying status should be vagrant.NOT_CREATED"


def test_vm_lifecycle(vm_dir):
    """Test methods controlling the VM - init(), up(), suspend(), halt(), destroy()."""
    VAGRANT_DIR = f"{os.environ['HOME']}/.vagrant.d"
    VAGRANTFILE_CREATED = False

    v = vagrant.Vagrant(vm_dir)

    # Test init by removing Vagrantfile, since v.init() will create one.
    try:
        os.unlink(os.path.join(vm_dir, "Vagrantfile"))
    except FileNotFoundError:
        pass

    try:
        os.mkdir(VAGRANT_DIR, mode=0o755)
    except FileExistsError:
        pass

    if not os.path.isfile(f"{VAGRANT_DIR}/Vagrantfile"):
        with open(f"{VAGRANT_DIR}/Vagrantfile", "w", encoding="UTF-8") as config:
            config.write(
                'Vagrant.configure("2") do |config|\n  config.vbguest.auto_update = false if Vagrant.has_plugin?("vagrant-vbguest")\nend\n'
            )
            VAGRANTFILE_CREATED = True

    v.init(TEST_BOX_NAME)
    assert v.NOT_CREATED == v.status()[0].state

    validation = v.validate(vm_dir)
    assert validation.returncode == 0

    v.up()
    assert v.RUNNING == v.status()[0].state

    v.suspend()
    assert v.SAVED == v.status()[0].state

    v.halt()
    assert v.POWEROFF == v.status()[0].state

    v.destroy()
    assert v.NOT_CREATED == v.status()[0].state

    if VAGRANTFILE_CREATED:
        os.unlink(f"{VAGRANT_DIR}/Vagrantfile")


def test_vm_resumecycle(vm_dir):
    """Test methods controlling the VM - up(), suspend(), resume()."""
    v = vagrant.Vagrant(vm_dir)

    v.up()
    assert v.RUNNING == v.status()[0].state

    v.suspend()
    assert v.SAVED == v.status()[0].state

    v.resume()
    assert v.RUNNING == v.status()[0].state


def test_valid_config(vm_dir):
    v = vagrant.Vagrant(vm_dir)
    v.up()
    validation = v.validate(vm_dir)
    assert validation.returncode == 0


def test_vm_config(vm_dir):
    """
    Test methods retrieving ssh config settings, like user, hostname, and port.
    """
    v = vagrant.Vagrant(vm_dir)
    v.up()
    command = [VAGRANT_EXE, "ssh-config"]
    ssh_config = compat.decode(subprocess.check_output(command, cwd=vm_dir))
    parsed_config = dict(
        line.strip().split(None, 1)
        for line in ssh_config.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    user = v.user()
    expected_user = parsed_config["User"]
    assert user == expected_user

    hostname = v.hostname()
    expected_hostname = parsed_config["HostName"]
    assert hostname, expected_hostname

    port = v.port()
    expected_port = parsed_config["Port"]
    assert port == expected_port

    user_hostname = v.user_hostname()
    assert user_hostname == "{}@{}".format(expected_user, expected_hostname)

    user_hostname_port = v.user_hostname_port()
    assert user_hostname_port == "{}@{}:{}".format(
        expected_user, expected_hostname, expected_port
    )

    keyfile = v.keyfile()
    try:
        assert keyfile == parsed_config["IdentityFile"]
    except AssertionError:
        # Vagrant 1.8 adds quotes around the filepath for the private key.
        assert keyfile == parsed_config["IdentityFile"].lstrip('"').rstrip('"')


def test_vm_sandbox_mode(vm_dir):
    """
    Test methods for enabling/disabling the sandbox mode
    and committing/rolling back changes.

    This depends on the Sahara plugin.
    """
    # Only test Sahara if it is installed.
    # This leaves the testing of Sahara to people who care.
    sahara_installed = _plugin_installed(vagrant.Vagrant(vm_dir), "sahara")
    if not sahara_installed:
        return

    v = vagrant.SandboxVagrant(vm_dir)

    sandbox_status = v.sandbox_status()
    assert (
        sandbox_status == "unknown"
    ), "Before the VM goes up the status should be 'unknown', " + "got:'{}'".format(
        sandbox_status
    )

    v.up()
    sandbox_status = v.sandbox_status()
    assert (
        sandbox_status == "off"
    ), "After the VM goes up the status should be 'off', " + "got:'{}'".format(
        sandbox_status
    )

    v.sandbox_on()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "on", (
        "After enabling the sandbox mode the status should be 'on', "
        + "got:'{}'".format(sandbox_status)
    )

    v.sandbox_off()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "off", (
        "After disabling the sandbox mode the status should be 'off', "
        + "got:'{}'".format(sandbox_status)
    )

    v.sandbox_on()
    v.halt()
    sandbox_status = v.sandbox_status()
    assert (
        sandbox_status == "on"
    ), "After halting the VM the status should be 'on', " + "got:'{}'".format(
        sandbox_status
    )

    v.up()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "on", (
        "After bringing the VM up again the status should be 'on', "
        + "got:'{}'".format(sandbox_status)
    )

    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    assert test_file_contents is None, "There should be no test file"

    _write_test_file(v, "foo")
    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    assert test_file_contents == "foo", "The test file should read 'foo'"

    v.sandbox_rollback()
    time.sleep(10)  # https://github.com/jedi4ever/sahara/issues/16

    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    assert test_file_contents is None, "There should be no test file"

    _write_test_file(v, "foo")
    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    assert test_file_contents == "foo", "The test file should read 'foo'"
    v.sandbox_commit()
    _write_test_file(v, "bar")
    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    assert test_file_contents == "bar", "The test file should read 'bar'"

    v.sandbox_rollback()
    time.sleep(10)  # https://github.com/jedi4ever/sahara/issues/16

    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    assert test_file_contents == "foo", "The test file should read 'foo'"

    sandbox_status = v._parse_vagrant_sandbox_status("Usage: ...")
    assert sandbox_status == "not installed", (
        "When 'vagrant sandbox status'"
        + " outputs vagrant help status should be 'not installed', "
        + "got:'{}'".format(sandbox_status)
    )

    v.destroy()
    sandbox_status = v.sandbox_status()
    assert (
        sandbox_status == "unknown"
    ), "After destroying the VM the status should be 'unknown', " + "got:'{}'".format(
        sandbox_status
    )


def test_boxesvm(test_dir):
    """
    Test methods for manipulating boxes - adding, listing, removing.
    """
    v = vagrant.Vagrant(test_dir)
    box_name = "python-vagrant-dummy-box"
    provider = f"{TEST_PROVIDER}"

    # Start fresh with no dummy box
    if box_name in list_box_names():
        subprocess.check_call([f"{VAGRANT_EXE}", "box", "remove", box_name])

    # Test that there is no dummy box listed
    assert box_name not in [
        b.name for b in v.box_list()
    ], "There should be no dummy box before it's added."
    # Add a box
    v.box_add(box_name, TEST_DUMMY_BOX_URL)

    # Test that there is a dummy box listed
    box_listing = v.box_list()
    assert (box_name, provider) in [
        (b.name, b.provider) for b in box_listing
    ], "The box {box} for provider {provider} should be in the list returned by box_list(). box_list()={box_listing}".format(
        box=box_name, provider=provider, box_listing=box_listing
    )

    # Remove dummy box using a box name and provider
    v.box_remove(box_name, provider)

    # Test that there is no dummy box listed
    assert box_name not in [
        b.name for b in v.box_list()
    ], "There should be no dummy box after it has been removed."


@pytest.mark.parametrize("vm_dir", (SHELL_PROVISION_VAGRANTFILE,), indirect=True)
def test_provisioning(vm_dir):
    """
    Test provisioning support.  The tested provision config creates a file on
    the vm with the contents 'foo'.
    """
    v = vagrant.Vagrant(vm_dir)

    v.up(no_provision=True)
    test_file_contents = _read_test_file(v)
    assert test_file_contents is None, "There should be no test file after up()"

    v.provision()
    test_file_contents = _read_test_file(v)
    print("Contents: {}".format(test_file_contents))
    assert test_file_contents == "foo", "The test file should contain 'foo'"


@pytest.mark.parametrize("vm_dir", (MULTIVM_VAGRANTFILE,), indirect=True)
def test_multivm_lifecycle(vm_dir):
    v = vagrant.Vagrant(vm_dir)

    # test getting multiple statuses at once
    assert v.status(VM_1)[0].state == v.NOT_CREATED
    assert v.status(VM_2)[0].state == v.NOT_CREATED

    v.up(vm_name=VM_1)
    assert v.status(VM_1)[0].state == v.RUNNING
    assert v.status(VM_2)[0].state == v.NOT_CREATED

    # start both vms
    v.up()
    assert v.status(VM_1)[0].state == v.RUNNING
    assert v.status(VM_2)[0].state == v.RUNNING

    v.halt(vm_name=VM_1)
    assert v.status(VM_1)[0].state == v.POWEROFF
    assert v.status(VM_2)[0].state == v.RUNNING

    v.destroy(vm_name=VM_1)
    assert v.status(VM_1)[0].state == v.NOT_CREATED
    assert v.status(VM_2)[0].state == v.RUNNING

    v.suspend(vm_name=VM_2)
    assert v.status(VM_1)[0].state == v.NOT_CREATED
    assert v.status(VM_2)[0].state == v.SAVED

    v.destroy(vm_name=VM_2)
    assert v.status(VM_1)[0].state == v.NOT_CREATED
    assert v.status(VM_2)[0].state == v.NOT_CREATED


@pytest.mark.parametrize("vm_dir", (MULTIVM_VAGRANTFILE,), indirect=True)
def test_multivm_config(vm_dir):
    """
    Test methods retrieving configuration settings.
    """
    v = vagrant.Vagrant(vm_dir, quiet_stdout=False, quiet_stderr=False)
    v.up(vm_name=VM_1)
    command = [VAGRANT_EXE, "ssh-config", VM_1]
    ssh_config = compat.decode(subprocess.check_output(command, cwd=vm_dir))
    parsed_config = dict(
        line.strip().split(None, 1)
        for line in ssh_config.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    user = v.user(vm_name=VM_1)
    expected_user = parsed_config["User"]
    assert user == expected_user

    hostname = v.hostname(vm_name=VM_1)
    expected_hostname = parsed_config["HostName"]
    assert hostname == expected_hostname

    port = v.port(vm_name=VM_1)
    expected_port = parsed_config["Port"]
    assert port == expected_port

    user_hostname = v.user_hostname(vm_name=VM_1)
    assert user_hostname == "{}@{}".format(expected_user, expected_hostname)

    user_hostname_port = v.user_hostname_port(vm_name=VM_1)
    assert user_hostname_port == "{}@{}:{}".format(
        expected_user, expected_hostname, expected_port
    )

    keyfile = v.keyfile(vm_name=VM_1)
    try:
        assert keyfile == parsed_config["IdentityFile"]
    except AssertionError:
        # Vagrant 1.8 adds quotes around the filepath for the private key.
        assert keyfile == parsed_config["IdentityFile"].lstrip('"').rstrip('"')


def test_ssh_command(vm_dir):
    """
    Test executing a command via ssh on a vm.
    """
    v = vagrant.Vagrant(vm_dir)
    v.up()
    output = v.ssh(command="echo hello")
    assert output.strip() == "hello"


@pytest.mark.parametrize("vm_dir", (MULTIVM_VAGRANTFILE,), indirect=True)
def test_ssh_command_multivm(vm_dir):
    """
    Test executing a command via ssh on a specific vm
    """
    v = vagrant.Vagrant(vm_dir)
    v.up()
    output = v.ssh(vm_name=VM_1, command="echo hello")
    assert output.strip() == "hello"
    output = v.ssh(vm_name=VM_2, command="echo I like your hat")
    assert output.strip() == "I like your hat"


def test_streaming_output(vm_dir):
    """
    Test streaming output of up or reload.
    """
    test_string = "Machine already provisioned"
    v = vagrant.Vagrant(vm_dir)

    with pytest.raises(subprocess.CalledProcessError):
        v.up(vm_name="incorrect-name")

    streaming_up = False
    for line in v.up(stream_output=True):
        print("output line:", line)
        if test_string in line:
            streaming_up = True

    assert streaming_up

    streaming_reload = False
    for line in v.reload(stream_output=True):
        print("output line:", line)
        if test_string in line:
            streaming_reload = True

    assert streaming_reload


def test_make_file_cm(test_dir):
    filename = os.path.join(test_dir, "test.log")
    if os.path.exists(filename):
        os.remove(filename)

    # Test writing to the filehandle yielded by cm
    cm = vagrant.make_file_cm(filename)
    with cm() as fh:
        fh.write("one\n")

    with open(filename, encoding="utf-8") as read_fh:
        assert read_fh.read() == "one\n"

    # Test appending to the file yielded by cm
    with cm() as fh:
        fh.write("two\n")

    with open(filename, encoding="utf-8") as read_fh:
        assert read_fh.read() == "one\ntwo\n"


def test_vagrant_version():
    v = vagrant.Vagrant()
    VAGRANT_VERSION = v.version()
    sys.stdout.write(f"vagrant_version(): {VAGRANT_VERSION}\n")
    version_result = bool(re.match("^[0-9.]+$", VAGRANT_VERSION))
    assert version_result is True


def _execute_command_in_vm(v, command):
    """
    Run command via ssh on the test vagrant box.  Returns a tuple of the
    return code and output of the command.
    """
    # ignore the fact that this host is not in our known hosts
    ssh_command = [VAGRANT_EXE, "ssh", "-c", command]
    return compat.decode(subprocess.check_output(ssh_command, cwd=v.root))


def _write_test_file(v, file_contents):
    """
    Writes given contents to the test file.
    """
    command = "echo '{}' > {}".format(file_contents, TEST_FILE_PATH)
    _execute_command_in_vm(v, command)


def _read_test_file(v):
    """
    Returns the contents of the test file stored in the VM or None if there
    is no file.
    """
    command = "cat {}".format(TEST_FILE_PATH)
    try:
        output = _execute_command_in_vm(v, command)
        return output.strip()
    except subprocess.CalledProcessError:
        return None


def _plugin_installed(v, plugin_name):
    plugins = v.plugin_list()
    return plugin_name in [plugin.name for plugin in plugins]
