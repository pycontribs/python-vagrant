"""
Tests for the various functionality provided by the VagrantTestCase class

There are a handful of classes to try to provide multiple different varying samples of possible setups
"""
import os
from vagrant import Vagrant
from vagrant.test import VagrantTestCase


def get_vagrant_root(test_vagrant_root_path):
    return os.path.dirname(os.path.realpath(__file__)) + '/vagrantfiles/' + test_vagrant_root_path

SINGLE_BOX = get_vagrant_root('single_box')
MULTI_BOX = get_vagrant_root('multi_box')


class AllMultiBoxesTests(VagrantTestCase):
    """Tests for a multiple box setup where vagrant_boxes is left empty"""

    vagrant_root = MULTI_BOX

    def test_default_boxes_list(self):
        """Tests that all boxes in a Vagrantfile if vagrant_boxes is not defined"""
        self.assertGreater(len(self.vagrant_boxes), 0)


class SingleBoxTests(VagrantTestCase):
    """Tests for a single box setup"""

    vagrant_root = SINGLE_BOX

    def test_box_up(self):
        """Tests that the box starts as expected"""
        state = self.vagrant.status(vm_name=self.vagrant_boxes[0])[0].state
        self.assertEqual(state, Vagrant.RUNNING)


class SpecificMultiBoxTests(VagrantTestCase):
    """Tests for a multiple box setup where only some of the boxes are to be on"""

    vagrant_boxes = ['precise32']
    vagrant_root = MULTI_BOX

    def test_all_boxes_up(self):
        """Tests that all boxes listed are up after starting"""
        for box_name in self.vagrant_boxes:
            state = self.vagrant.status(vm_name=box_name)[0].state
            self.assertEqual(state, Vagrant.RUNNING)

    def test_unlisted_boxes_ignored(self):
        """Tests that the boxes not listed are not brought up"""
        for box_name in [s.name for s in self.vagrant.status()]:
            if box_name in self.vagrant_boxes:
                self.assertBoxUp(box_name)
            else:
                self.assertBoxNotCreated(box_name)
