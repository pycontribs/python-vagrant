"""Tests for the various functionality provided by the VagrantTestCase class"""
import os
from vagrant import Vagrant
from vagrant.test import VagrantTestCase


def get_vagrant_root(test_vagrant_root_path):
	return os.path.dirname(os.path.realpath(__file__)) + '/vagrantfiles/' + test_vagrant_root_path


class SingleBoxTests(VagrantTestCase):
	"""Some tests covering the basic functionality of the VagrantTestCase class"""

	vagrant_boxes = ['default']
	vagrant_root = get_vagrant_root('single_box')

	def test_box_starts(self):
		self.assertEqual(self.vagrant.status()['default'], Vagrant.RUNNING)


class MultiBoxTests(VagrantTestCase):
	"""Tests for a multiple box setup"""

	vagrant_boxes = ['precise32', 'precise64']
	vagrant_root = get_vagrant_root('multi_box')

	def test_all_boxes_up(self):
		for box_name in self.vagrant_boxes:
			self.assertEqual(self.vagrant.status()[box_name], Vagrant.RUNNING)