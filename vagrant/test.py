"""
A TestCase class, tying together the Vagrant class and removing some of the boilerplate involved in writing tests
that leverage vagrant boxes.
"""
from unittest import TestCase
from vagrant import Vagrant, stderr_cm

__author__ = 'nick'


class VagrantTestCase(TestCase):
	"""
	TestCase class to control vagrant boxes during testing

	vagrant_boxes: An iterable of vagrant boxes. If empty or None, all boxes will be used. Defaults to []
	vagrant_root: The root directory that holds a Vagrantfile for configuration. Defaults to the working directory
	restart_boxes: If True, the boxes will be restored to their initial states between each test, otherwise the boxes
		will remain up. Defaults to False
	"""

	vagrant_boxes = []
	vagrant_root = None
	restart_boxes = False

	__initial_box_statuses = {}
	__cleanup_actions = {
		Vagrant.NOT_CREATED: 'destroy',
		Vagrant.POWEROFF: 'halt',
		Vagrant.SAVED: 'suspend',
	}

	def __init__(self, *args, **kwargs):
		"""Check that the vagrant_boxes attribute is not left empty, and is populated by all boxes if left blank"""
		self.vagrant = Vagrant(self.vagrant_root, err_cm=stderr_cm)
		if not self.vagrant_boxes:
			boxes = [s.name for s in self.vagrant.status()]
			if len(boxes) == 1:
				self.vagrant_boxes = ['default']
			else:
				self.vagrant_boxes = boxes
		super(VagrantTestCase, self).__init__(*args, **kwargs)

	def assertBoxStatus(self, box, status):
		"""Assertion for a box status"""
		box_status = [s.state for s in self.vagrant.status() if s.name == box][0]
		if box_status != status:
			self.failureException('{} has status {}, not {}'.format(box, box_status, status))

	def assertBoxUp(self, box):
		"""Assertion for a box being up"""
		self.assertBoxStatus(box, Vagrant.RUNNING)

	def assertBoxSuspended(self, box):
		"""Assertion for a box being up"""
		self.assertBoxStatus(box, Vagrant.SAVED)

	def assertBoxHalted(self, box):
		"""Assertion for a box being up"""
		self.assertBoxStatus(box, Vagrant.POWEROFF)

	def assertBoxNotCreated(self, box):
		"""Assertion for a box being up"""
		self.assertBoxStatus(box, Vagrant.NOT_CREATED)

	def run(self, result=None):
		"""Override run to have provide a hook into an alternative to tearDownClass with a reference to self"""
		self.setUpOnce()
		run = super(VagrantTestCase, self).run(result)
		self.tearDownOnce()
		return run

	def setUpOnce(self):
		"""Collect the box states before starting"""
		for box_name in self.vagrant_boxes:
			box_state = [s.state for s in self.vagrant.status() if s.name == box_name][0]
			self.__initial_box_statuses[box_name] = box_state

	def tearDownOnce(self):
		"""Restore all boxes to their initial states after running all tests, unless tearDown handled it already"""
		if not self.restart_boxes:
			self.restore_box_states()

	def restore_box_states(self):
		"""Restores all boxes to their original states"""
		for box_name in self.vagrant_boxes:
			action = self.__cleanup_actions.get(self.__initial_box_statuses[box_name])
			if action:
				getattr(self.vagrant, action)(vm_name=box_name)

	def setUp(self):
		"""Starts all boxes before running tests"""
		for box_name in self.vagrant_boxes:
			self.vagrant.up(vm_name=box_name)

		super(VagrantTestCase, self).setUp()

	def tearDown(self):
		"""Returns boxes to their initial status after each test if self.restart_boxes is True"""
		if self.restart_boxes:
			self.restore_box_states()

		super(VagrantTestCase, self).tearDown()
