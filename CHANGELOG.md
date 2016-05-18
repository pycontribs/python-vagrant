
# Changelog

This document lists the changes (and individuals who contributed to those
changes) for each release of python-vagrant.

## 0.5.13

- Pull Request #50: Filter out unneeded status lines for AWS instances
  Author: Brian Berry (https://github.com/bryanwb)

## 0.5.11

- Pull Request #47: Add support for snapshot command (vagrant version >= 1.8.0)
  Author: Renat Zaripov (https://github.com/rrzaripov)

## 0.5.10

- Pull Request 46: Adds support for Vagrant 1.8 `--machine-readable` changes.
  See https://github.com/todddeluca/python-vagrant/pull/46.
  Author: Conor (https://github.com/conorsch)

## 0.5.9

- Support Python 3 in addition to Python 2
  Author: Volodymyr Vitvitskyi (https://github.com/signalpillar)
- Use `os.devnull` for Windows compatability.
  Author: Renat Zaripov (https://github.com/rrzaripov)


## 0.5.8

- Fix regression where vagrant commands were being printed to stdout.
  Author: Todd DeLuca (https://github.com/todddeluca)


## 0.5.7

- Allow redirection of the output of the vagrant command subprocess to a file.

  In order to log the output of the subprocess that runs vagrant commands,
  or alternatively to silence that output, `Vagrant.__init__` accepts two
  parameters, `out_cm` and `err_cm` that are no-argument functions that, when
  executed, return a context manager that yields a filehandle, etc., suitable
  for use with the `stdout` and `stderr` parameters of `subprocess.Popen`.
  Author: Manuel Sanchez (https://github.com/omoman)
  Author: Todd DeLuca (https://github.com/todddeluca)


## 0.5.6

- add instance attribute `Vagrant.env` which is a mapping of environment
  variables to be passed to the vagrant subprocess when invoked. This allows
  basic inter-process communication between Python and Vagrant via environment
  variables.
  Author: Alex Conrad (https://github.com/aconrad)

- `Vagrant.__init__` now accepts a keyword argument `env=None` which will be
  assigned to the instance attribute `Vagrant.env`.
  Author: Alex Conrad (https://github.com/aconrad)


## 0.5.5

Oops.  Pushed non-master branch to PyPI, for version 0.5.4.  Pushing master
branch for 0.5.5.


## 0.5.4

The major change in this version is switching to using `--machine-readable` in
some vagrant commands to make the underlying `vagrant` commands return
easily-parseable output.  The `--machine-readable` option requires Vagrant 1.4
or higher.

- Use `--machine-readable` output for `status`, `box_list`, and `plugin_list`.
- Allow arbitrary status codes, so new statuses do not break parsing.
  Previously, statuses were constrained to known ones for the sake of parsing.
  Now that machine-readable vagrant output is being used, any status can be
  parsed.
- Status value constants (e.g. vagrant.Vagrant.NOT_CREATED) have changed to
  match the "state" value returned by the `--machine-readable` output of
  the `vagrant status` command.
- The box version is now returned for a box listing

## 0.5.3

- Add box update command.
  Author: Alex Lourie (https://github.com/alourie)

## 0.5.2

- Add resume command.
  Author: Renat Zaripov (https://github.com/rrzaripov)
  
## 0.5.1

- Find the correct executable on Cygwin systems.  See `which` and
  https://github.com/todddeluca/python-vagrant/issues/26.
  Author: Todd DeLuca (https://github.com/todddeluca)

## 0.5.0 (release 2014/03/25)

This is a backwards-incompatible release with a number of breaking changes to
the API.  Some of these changes were made to bring the python-vagrant API more
closely in line with the vagrant CLI, a key design goal of python-vagrant.
Other changes simplify the code.  This release also includes a number of pull
requests.

Major (backwards-incompatible) changes:

- Fix inconsistencies between python-vagrant and the vagrant CLI.

  A goal of the design of methods like `status()`, `box_list()`, and
  `plugin_list()` is to be a thin wrapper around the corresponding vagrant CLI
  commands, with a very similar API.  These changes bring python-vagrant closer
  to that goal, I hope.

  When status() was originally written, it was with single-VM environments
  in mind, before provider information was available.  Since then it was
  altered to return a dict to handle multi-VM environments.  However it
  still did not return the provider information vagrant outputs.  This
  command updates the status API so that it returns every tuple of VM name
  (i.e. target), state (i.e. status), and provider output by the
  underlying vagrant command.  These tuples of values are returned as a
  list of Status classes.  The decision to return a list of Statuses
  instead of a dict mapping VM name to Status was made because the vagrant
  CLI does not make clear that the status information it returns can be
  keyed on VM name.  In the case of `vagrant box list`, box names can be
  repeated if there are multiple version of boxes.  Therefore, returning a
  list of Statuses seemed more consistent with (my understanding of)
  vagrant's API.

  The box_list() method was originally written, as I recall, before
  providers and versions were a part of Vagrant.  Then box_list_long() was
  written to accommodate provider information, without changing the
  box_list() API.  Unfortunately, this meant box_list() diverged more from
  the output of `vagrant box list`.  To bring the python-vagrant API back
  in line with the vagrant API, while keeping it simple, the
  box_list_long() method is being removed and the box_list() method is
  being updated to return a list of Box instances.  Each box instance
  contains the information that the `vagrant box list` command returns for
  a box, the box name, provider, and version.  The user who wants a list
  of box names can do:

      [box.name for box in v.box_list()]

  For consistency with status() and box_list(), the relatively new
  plugin_list() command is updated to return a list of Plugin objects
  instead of a list of dicts containing the plugin info from vagrant.

  The choice to use classes for Status, Box, and Plugin information was
  motivated by the lower syntactic weight compared to using a dicts.
  Author: Todd DeLuca (https://github.com/todddeluca)
- Pull Request #22.  Don't die if vagrant executable is missing when the vagrant module is imported.  Wait until the Vagrant class is used.
  Author: Gertjan Oude Lohuis (https://github.com/gertjanol)
- Move verbosity/quiet flags from `**kwargs` to instance vars.

  Unfortunately, this is a breaking change for people who use these keywords.
  Nevertheless, the proliferation of `**kwargs` in the method signatures is a bad
  smell.  The code is not self documenting.  It is not clear from the code what
  keywords you can pass, and it will accept keywords it does not use.  Also, as
  new methods are added, their signatures must be polluted either by the vague
  `**kwargs` or a host of seemingly irrelevant keywords, like capture_output and
  quiet_stderr.        Moving the verbosity and quietness functions to instance
  variables from   function parameters makes their functionality more well
  documented,   simplifies and makes more explicit  many method signatures, and
  maintains the desired functionality.

  For a "loud" instance, use vagrant.Vagrant(quiet_stdout=False).  Set quiet_stderr=False for an even louder version.

  In keeping with past behavior, vagrant instances are quiet by default.
  Author: Todd DeLuca (https://github.com/todddeluca)

Other minor changes and fixes:

- Pull Request #21.  Fix Sandbox Tests
  Author: Gertjan Oude Lohuis (https://github.com/gertjanol)
- Split internal _run_vagrant_command method into _run_vagrant_command (for capturing output) and _call_vagrant_command (when output is not needed, e.g. for parsing).
  Author: Todd DeLuca (https://github.com/todddeluca)
- Fix provisioning test.
  Author: Todd DeLuca (https://github.com/todddeluca)

## 0.4.5 (released 2014/03/22)

- Add a 'quiet_stderr' keyword to silence the stderr output of vagrant commands.
  Author: Rich Smith (https://github.com/MyNameIsMeerkat).  The original author of the pull request
  Author: Todd DeLuca.  Split the pull request and tweaked the code.
- Disable broken SandboxVagrant tests.  Does a Sahara user want to fix these tests?
  Author: Todd DeLuca.

## 0.4.4 (released 2014/03/21)

This minor release *should* be backwards-compatible.
Add a 'reload' command, which the Vagrant docs describe as akin to a "halt" followed by an "up".
Add a 'plugin list' command that returns a list of installed plugins.
Add 'version' command, which gives programmatic access to the vagrant version string.
Add '--provision-with' option to 'up', 'provision', and 'reload' commands.
Author: Todd DeLuca (https://github.com/todddeluca)

Add support LXC statuses 'frozen' and 'stopped'
Author: Allard Hoeve (https://github.com/allardhoeve)


## 0.4.3 (released 2013/12/18)

Allow the underlying vagrant command output to be visible on the command line.
Author: Alexandre Joseph (https://github.com/jexhson)


## 0.4.2 (released 2013/12/08)

This release fixes a bug in setup.py.
Author: Nick Allen (https://github.com/nick-allen).


## 0.4.1 (released 2013/12/08)

This release includes improved testing, including a new VagrantTestCase.
Author: Nick Allen (https://github.com/nick-allen).


## 0.4.0 (released 2013/07/30)

To indicate that this release includes a significant backwards-incompatible API
change to `status`, the minor version number is being bumped.

Backwards-incompatible enhancements and bug fixes:

- Return a dictionary from `status()` in all cases, instead of returning None
  for no status found, the status string for a single-VM or multi-VM with a
  VM name specified, or a dictionary for the multi-VM case.  This change makes
  the return value more consistent.  It also more closely parallels the return
  value of the underlying `vagrant status` call.
  Author: Alek Storm (https://github.com/alekstorm)
  Author: Todd DeLuca (https://github.com/todddeluca) fixed tests.

Enhancements and bug fixes:

- Add ability for up to take a provider option
  Author: Brett Cooley (https://github.com/brcooley)


## 0.3.1 (released 2013/05/09)

This release includes two bug fixes aimed at getting vagrant commands to work
on Windows:

- Use explicit vagrant executable instead of 'vagrant' in subprocess commands.
  Author: Mohan Raj Rajamanickam (https://github.com/mohanraj-r)
- Fix 'which' command so that it finds the vagrant executable on the PATH in
  Windows.
  Author: Todd DeLuca (https://github.com/todddeluca)
  Windows Tester: Mohan Raj Rajamanickam (https://github.com/mohanraj-r)

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
