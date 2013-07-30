## Introduction

Python-vagrant is a python module that provides a _thin_ wrapper around the
`vagrant` command line executable, allowing programmatic control of Vagrant
virtual machines (boxes).  This module is useful for:

- Starting a Vagrant box (`up`).
- Terminating a Vagrant box (`destroy`).
- Halting a Vagrant box without destroying it (`halt`).
- Querying the status of a box (`status`).
- Getting ssh configuration information useful for SSHing into the box. (`host`, `port`, ...)
- Running `vagrant` commands in a multi-VM environment
  (http://vagrantup.com/v1/docs/multivm.html) by using `vm_name` parameter.
- Initializing the VM based on a named base box, using init().
- Adding, Removing, and Listing boxes (`box add`, `box remove`, `box list`).
- Provisioning - up() accepts no_provision and there is a provision() method.
- Using sandbox mode from the Sahara gem (https://github.com/jedi4ever/sahara).

This package is _alpha_ and its API is not guaranteed to be stable.  The API
attempts to be congruent with the `vagrant` API terminology, to facilitate
knowledge transfer for users already familiar with Vagrant.

I wanted python bindings for Vagrant so I could programmatically access my
vagrant box using Fabric.  Drop me a line to let me know how you use
python-vagrant.  -Todd DeLuca


## Contribute

If you use python and vagrant and this project does not do what you want,
please open an issue or a pull request on github at
https://github.com/todddeluca/python-vagrant.

Please see CHANGELOG.md for a detailed list of contributions and authors.

When making a pull request, please include unit tests that test your changes
and make sure any existing tests still work.  One can test with:

    cd /path/to/python-vagrant
    nosetests


## Requirements

- Vagrant 1.1 or greater (Currently tested with 1.1.5).
- Vagrant requires VirtualBox (e.g. VirtualBox 4.2.10) or another provider.
- Python 2.7 (the only version this package has been tested with.)
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
