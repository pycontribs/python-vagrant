"""
A TestCase class, tying together the Vagrant class and removing some of the boilerplate involved in writing tests
that leverage vagrant boxes.
"""
from unittest import TestCase
from vagrant import Vagrant

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

	def __new__(cls, *args):
		"""
		Give the class access to a vagrant attribute that uses the vagrant_root attribute provided in the class definition
		"""
		cls.vagrant = Vagrant(cls.vagrant_root)
		return super(VagrantTestCase, cls).__new__(cls, *args)

	def __init__(self, *args, **kwargs):
		"""Check that the vagrant_boxes attribute is not left empty, and is populated by all boxes if left blank"""
		if not self.vagrant_boxes:
			boxes = self.vagrant.status().keys()
			if len(boxes) == 1:
				self.vagrant_boxes = ['default']
			else:
				self.vagrant_boxes = boxes
		super(VagrantTestCase, self).__init__(*args, **kwargs)

	@classmethod
	def tearDownClass(cls):
		"""Restore all boxes to their initial states after running all tests, unless tearDown handled it already"""
		if not cls.restart_boxes:
			cls.restore_box_states()

	@classmethod
	def restore_box_states(cls):
		"""Restores all boxes to their original states"""
		for box_name in cls.vagrant_boxes:
			action = cls.__cleanup_actions.get(cls.__initial_box_statuses[box_name])
			if action:
				getattr(cls.vagrant, action)(vm_name=box_name)

	def setUp(self):
		"""Starts all boxes before running tests"""
		for box_name in self.vagrant_boxes:

			self.__initial_box_statuses[box_name] = self.vagrant.status()[box_name]
			self.vagrant.up(vm_name=box_name)

		super(VagrantTestCase, self).setUp()

	def tearDown(self):
		"""Returns boxes to their initial status after each test if self.restart_boxes is True"""
		if self.restart_boxes:
			self.restore_box_states()

		super(VagrantTestCase, self).tearDown()