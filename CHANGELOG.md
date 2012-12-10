
# Changelog

This document lists the changes (and individuals who contributed to those
changes) for each release of python-vagrant.


## 0.2.0 (released 2012/12/09)

This release incorporates numerous changes from a couple of forks on github:
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
- A new subclass, SandboxVagrant, for using the sandbox extensions from the
  Sahara gem.
  Author: Todd DeLuca (https://github.com/todddeluca).


## 0.1.0 (released 2012/06/07)

This is the original release of python-vagrant as its own package.

- Author: Todd DeLuca (https://github.com/todddeluca).




