## Introduction

Python-vagrant is a python module that provides a _thin_ wrapper around the
`vagrant` command line executable, allowing programmatic control of Vagrant
virtual machines (boxes).  This module is useful for:

- Starting a Vagrant virtual machine (VM) (`up`).
- Terminating a Vagrant VM (`destroy`).
- Halting a Vagrant VM without destroying it (`halt`).
- Querying the status of a VM or VMs (`status`).
- Getting ssh configuration information useful for SSHing into the VM. (`host`, `port`, ...)
- Running `vagrant` commands in a multi-VM environment
  (http://vagrantup.com/v1/docs/multivm.html) by using `vm_name` parameter.
- Initializing the VM based on a named base box, using init().
- Adding, Removing, and Listing boxes (`box add`, `box remove`, `box list`).
- Provisioning VMs - up() accepts options like `no_provision`, `provision`, and `provision_with`, and there is a `provision()` method.
- Using sandbox mode from the Sahara gem (https://github.com/jedi4ever/sahara).

This project began because I wanted python bindings for Vagrant so I could
programmatically access my vagrant box using Fabric.  Drop me a line to let me
know how you use python-vagrant.  I'd love to share more use cases.  -Todd DeLuca


## Versioning and API Stability

This package is _beta_ and its API is not guaranteed to be stable.  The API
attempts to be congruent with the `vagrant` API terminology, to facilitate
knowledge transfer for users already familiar with Vagrant.  Over time, the
python-vagrant API has changed to better match the underling `vagrant` CLI and
to evolve with the changes in that CLI.

The package version numbering is in the form `0.X.Y`.  The initial `0` reflects
the _beta_ nature of this project.  The number `X` is incremented when
backwards-incompatible changes occur.  The number `Y` is incremented when
backwards-compatible features or bug fixes are added.


## Requirements

- Vagrant 1.4 or greater (currently tested with 1.7.2).  Using the latest
  version of Vagrant is strongly recommended.
- Vagrant requires VirtualBox, VMWare, or another supported provider.
- Python 2.7 (the only version this package has been tested with.) or Python
  3.3 or higher.
- The Sahara gem for Vagrant is optional.  It will allow you to use
  `SandboxVagrant`.


## Installation

### Install from pypi.python.org

Download and install python-vagrant:

    pip install python-vagrant

### Install from github.com

Clone and install python-vagrant

    cd ~
    git clone git@github.com:todddeluca/python-vagrant.git
    cd python-vagrant
    python setup.py install


## Usage

A contrived example of starting a vagrant box (using a Vagrantfile from the
current directory) and running a fabric task on it:

    import vagrant
    from fabric.api import env, execute, task, run

    @task
    def mytask():
        run('echo $USER')


    v = vagrant.Vagrant()
    v.up()
    env.hosts = [v.user_hostname_port()]
    env.key_filename = v.keyfile()
    env.disable_known_hosts = True # useful for when the vagrant box ip changes.
    execute(mytask) # run a fabric task on the vagrant host.

Another example showing how to use vagrant multi-vm feature with fabric:

    import vagrant
    from fabric.api import *

    @task
    def start(machine_name):
       """Starts the specified machine using vagrant"""
       v = vagrant.Vagrant()
       v.up(vm_name=machine_name)
       with settings(host_string= v.user_hostname_port(vm_name=machine_name),
                     key_filename = v.keyfile(vm_name=machine_name),
                     disable_known_hosts = True):
            run("echo hello")

By default python vagrant instances are quiet, meaning that they capture stdout
and stderr.  For a "loud" instance, use `vagrant.Vagrant(quiet_stdout=False)`.
Set `quiet_stderr=False` for an even louder version.

### Interacting With the Vagrant Subprocess

The `Vagrant` class works by executing `vagrant` commands in a subprocess and
interpreting the output.  Depending on the needs of the user, the communication
to and from the subprocess can be tailored by altering its environment and
where it sends its stdout and stderr.

#### Silencing the Stdout or Stderr of the Vagrant Subprocess

The stdout and stderr of the underlying vagrant process can be silenced by
using the `out_cm` and `err_cm` parameters, or by using the `quiet_stdout` and
`quiet_stderr` parameters of `Vagrant.__init__`.  

Using `out_cm` and `err_cm` to redirect stdout and stderr to `/dev/null`:

    v = vagrant.Vagrant(out_cm=vagrant.devnull_cm, err_cm=vagrant.devnull_cm)
    v.up() # normally noisy

Using `quiet_stdout` and `quiet_stderr` to redirect stdout and stderr to
`/dev/null`:

    v = vagrant.Vagrant(quiet_stdout=True, quiet_stderr=True)
    v.up() # normally noisy

These are functionally equivalent.

#### Logging the Stdout or Stderr of the Vagrant Subprocess

A user might wish to direct the stdout and stderr of a vagrant subprocess to
a file, perhaps to log and analyze the results of an automated process.  This
can be accomplished using the `out_cm` and `err_cm` parameters of
`Vagrant.__init__`.

For example, log the stdout and stderr of the subprocess to the file
'deployment.log':

    log_cm = vagrant.make_file_cm('deployment.log')
    v = vagrant.Vagrant(out_cm=log_cm, err_cm=log_cm)
    v.up() # normally noisy

#### Altering the Environment of the Vagrant Subprocess

It's possible to communicate with the Vagrant subprocess using environment
variables. The `Vagrantfile` could expect environment variables to be present
and act accordingly. The environment variables can be set by `python-vagrant`.

```python
import vagrant

v = vagrant.Vagrant()

os_env = os.environ.copy()
os_env['USE_NFS'] = '1'

v.env = os_env
v.up()  # will pass env to the vagrant subprocess
```

Alternatively, the environment can be passed at instantiation time.

```python
import vagrant

os_env = os.environ.copy()
os_env['USE_NFS'] = '1'

v = vagrant.Vagrant(env=env)
assert v.env is env  # True
v.up()  # will pass env to the vagrant subprocess
```

## Contribute

If you use python and vagrant and this project does not do what you want,
please open an issue or a pull request on github at
https://github.com/todddeluca/python-vagrant.

Please see CHANGELOG.md for a detailed list of contributions and authors.

When making a pull request, please include unit tests that test your changes
and make sure any existing tests still work.  See the Testing section below.


## Testing

Running the full suite of tests might take 10 minutes or so.  It involves
downloading boxes and starting and stopping virtual machines several times.

Run the tests from the top-level directory of the repository:

    nosetests

Here is an example of running an individual test:

    nosetests tests.test_vagrant:test_boxes


Manual test of functionality for controlling where the vagrant subcommand
output is sent -- console or devnull:

    >>> import vagrant
    >>> import os
    >>> vagrantfile = '/Users/tfd/proj/python-vagrant/tests/vagrantfiles/single_box'
    >>> # Demonstrate a quiet Vagrant.  Equivalent to out_cm=vagrant.devnull_cm
    ... v1 = vagrant.Vagrant(vagrantfile)
    >>> v1.destroy() # output to /dev/null
    >>> # Demonstrate a loud Vagrant.  Equivalent to out_cm=vagrant.stdout_cm
    ... v2 = vagrant.Vagrant(vagrantfile, quiet_stdout=False)
    >>> v2.destroy() # stdout sent to console
    ==> default: VM not created. Moving on...
    >>> # Demonstrate that out_cm takes precedence over quiet_stdout=True
    ... v3 = vagrant.Vagrant(vagrantfile, out_cm=vagrant.stdout_cm)
    >>> v3.destroy() # output to console
    ==> default: VM not created. Moving on...
    >>> # Demonstrate a quiet Vagrant using devnull_cm directly
    ... v4 = vagrant.Vagrant(vagrantfile, out_cm=vagrant.devnull_cm)
    >>> v4.destroy() # output to console
    >>> 


