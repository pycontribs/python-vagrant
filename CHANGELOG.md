
# Changelog

This document lists the changes (and individuals who contributed to those
changes) for each release of python-vagrant.


## 0.3.0 (released 2013/04/12)

This release contains backwards-incompatible changes related to the changes in
Vagrant 1.1+.  Vagrant 1.1 introduces the concept of providers (like virtualbox
or vmware_fusion) which affect the API of `vagrant box` commands and the output
of `vagrant status` (and other commands).  

New functionality and bug fixes:

- Add new vm state: ABORTED
  Author: Robert Strind (https://github.com/stribert)
- Add new vm state: SAVED
  Author: Todd DeLuca (https://github.com/todddeluca)
- Fix parsing of vagrant 1.1 status messages.
  Author: Vincent Viallet (https://github.com/zbal)
  Author: Todd DeLuca (https://github.com/todddeluca)
- Add new lifecycle method, suspend(), corresponding to `vagrant suspend`.
  Author: Todd DeLuca (https://github.com/todddeluca)
- Fix parsing of vagrant 1.1 ssh config output.
  Author: Vincent Viallet (https://github.com/zbal)

Backwards-incompatible changes:

- Removed redundant `box_` prefix from `box_name` and `box_url` parameters
  in `box_add` and `box_remove` methods.  This aligns these parameter names
  with the parameter names in the corresponding vagrant CLI commands.
  Author: Todd DeLuca (https://github.com/todddeluca).
- Added required parameter `provider` to `box_remove` method.  This is
  consistent with the backwards-incompatible change in the underlying
  `vagrant box remove` command.
  Author: Todd DeLuca (https://github.com/todddeluca).
- Method `init`, corresponding to `vagrant init`, has been changed to more
  closely reflect `vagrant init`.  The parameter `box_path` has been changed
  to `box_url`.  The method no longer attempts to interactively add a box if
  it has not already been added.
  Author: Todd DeLuca (https://github.com/todddeluca).


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




