from unittest import TestCase
from vagrant import Vagrant

__author__ = 'nick'


class VagrantTestCase(TestCase):
	"""
	TestCase class to control vagrant boxes during testing

	vagrant_boxes: An iterable of vagrant boxes. A single box setup should have 'default' as the only box
	vagrant_root: The root directory that holds a Vagrantfile for configuration. Defaults to the working directory
	restart_boxes: If True, the boxes will be restored to their initial states between each test, otherwise the boxes
		will remain up. Defaults to True
	"""
	vagrant_boxes = []
	vagrant_root = None
	restart_boxes = True

	__initial_box_statuses = {}
	__cleanup_actions = {
		Vagrant.NOT_CREATED: 'destroy',
		Vagrant.POWEROFF: 'halt',
		Vagrant.SAVED: 'suspend',
	}

	def __new__(cls, *args):
		cls.vagrant = Vagrant(cls.vagrant_root)
		return super(VagrantTestCase, cls).__new__(cls, *args)

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