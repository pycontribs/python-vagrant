"""Tests for the various functionality provided by the VagrantTestCase class"""
import os
from vagrant import Vagrant
from vagrant.test import VagrantTestCase


def get_vagrant_root(test_vagrant_root_path):
	return os.path.dirname(os.path.realpath(__file__)) + '/vagrantfiles/' + test_vagrant_root_path

SINGLE_BOX = get_vagrant_root('single_box')
MULTI_BOX = get_vagrant_root('multi_box')


class BasicTests(VagrantTestCase):
	"""Some tests covering the basic functionality of the VagrantTestCase class"""

	vagrant_root = MULTI_BOX

	def test_default_boxes_list(self):
		"""Tests that all boxes in a Vagrantfile if vagrant_boxes is not defined"""
		self.assertGreater(len(self.vagrant_boxes), 0)


class SingleBoxTests(VagrantTestCase):
	"""Tests for a single box setup"""

	vagrant_boxes = ['default']
	vagrant_root = SINGLE_BOX

	def test_box_starts(self):
		self.assertEqual(self.vagrant.status()[self.vagrant_boxes[0]], Vagrant.RUNNING)


class MultiBoxTests(VagrantTestCase):
	"""Tests for a multiple box setup"""

	vagrant_boxes = ['precise32', 'precise64']
	vagrant_root = MULTI_BOX

	def test_all_boxes_up(self):
		for box_name in self.vagrant_boxes:
			self.assertEqual(self.vagrant.status()[box_name], Vagrant.RUNNING)