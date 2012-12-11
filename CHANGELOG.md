
# Changelog

This document lists the changes (and individuals who contributed to those
changes) for each release of python-vagrant.


## 0.2.0 (released 2012/12/09)

This release incorporates numerous changes from a couple of forks on github, 
https://github.com/kamilgrymuza/python-vagrant and
https://github.com/nithinbose87/python-vagrant.

- A rewritten test suite allowing easier addition of new features.  
  Author: Kamil Grymuza (https://github.com/kamilgrymuza).
- The init() method which initialized the VM based on the named base box.
  Author: Kamil Grymuza (https://github.com/kamilgrymuza).
- The halt() method which stops the VM without destroying it.
  Author: Kamil Grymuza (https://github.com/kamilgrymuza).
- Support for sandbox mode using the Sahara gem 
  (https://github.com/jedi4ever/sahara).
  Author: Kamil Grymuza (https://github.com/kamilgrymuza).
- Support for box-related commands - box_add(), box_list(), box_remove() methods. 
  Author: Kamil Grymuza (https://github.com/kamilgrymuza).
- Support for provisioning - up() accepts no_provision and there is the provision()
  method.
  Author: Kamil Grymuza (https://github.com/kamilgrymuza).
- Added auto download of official boxes in the init() 
  Author: Nithin Bose (https://github.com/nithinbose87).

Additionally, support for Multi-VM environments has been added, along with
several other changes:

- `vagrant.Vagrant` and `vagrant.SandboxVagrant` methods which support multi-VM
  environments through the `vm_name` parameter.
  Author: Todd DeLuca (https://github.com/todddeluca).
- A new subclass, SandboxVagrant, for using the sandbox extensions from the
  Sahara gem.  Method names in SandboxVagrant were changed to conform to the
  cli names of sandbox.  E.g. sandbox_enable() was changed to sandbox_on().
  This is in keeping with the goal of python-vagrant to stick closely to the
  nomenclature of vagrant.
  Author: Todd DeLuca (https://github.com/todddeluca).
- A rewritten `tests/test_vagrant.py` which removes a dependency on Fabric,
  adds tests for multi-VM functionality, and moves some setup and teardown up
  to the module level.
  Author: Todd DeLuca (https://github.com/todddeluca).
- Vagrant and SandboxVagrant no longer invoke subprocesses with `shell=True`.
  This way something like `vagrant ssh -c <command>` could be used without
  worry about how to quote the command.
  Author: Todd DeLuca (https://github.com/todddeluca).
- Configuration is now cached under the given vm_name, when relevant.
  Author: Todd DeLuca (https://github.com/todddeluca).
- `status()` now returns multiple statuses when in a multi-VM environment.
  Author: Todd DeLuca (https://github.com/todddeluca).
 
Please note that the changes to sandbox functionality are not
backwards-compatible with the kamilgrymuza fork, though updating the code to
use this project should be straightforward, should one want to do so.


## 0.1.0 (released 2012/06/07)

This is the original release of python-vagrant as its own package.

- Author: Todd DeLuca (https://github.com/todddeluca).




