# -*- coding: utf-8 -*-
#
# test_rate_neuron_communication.py
#
# This file is part of NEST.
#
# Copyright (C) 2004 The NEST Initiative
#
# NEST is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# NEST is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NEST.  If not, see <http://www.gnu.org/licenses/>.

# This test checks interactions between rate neurons, i.e.
# the delay, weight and nonlinearities of rate neurons.

import nest
import unittest
import math
import numpy as np


def H(x):
    return 0.5 * (np.sign(x) + 1.)


@nest.check_stack
class RateNeuronCommunicationTestCase(unittest.TestCase):

    """Check rate_neuron"""

    def setUp(self):
        # test parameter
        self.rtol = 0.05

        # neuron parameters
        self.neuron_params = {'tau': 5., 'std': 0.}
        self.drive = 1.5
        self.delay = 2.
        self.weight = 0.5

        # simulation parameters
        self.simtime = 100.
        self.dt = 0.1

        nest.set_verbosity('M_WARNING')
        nest.ResetKernel()
        nest.SetKernelStatus({'resolution': self.dt, 'use_wfr': True})

        # set up rate neuron network
        self.rate_neuron_drive = nest.Create(
            'lin_rate_ipn', params={'rate': self.drive,
                                    'mean': self.drive, 'std': 0.})

        self.rate_neuron_1 = nest.Create(
            'lin_rate_ipn', params=self.neuron_params)
        self.rate_neuron_2 = nest.Create(
            'tanh_rate_ipn', params=self.neuron_params)
        self.rate_neuron_3 = nest.Create(
            'threshold_lin_rate_ipn', params=self.neuron_params)

        self.multimeter = nest.Create("multimeter",
                                      params={'record_from': ['rate'],
                                              'interval': self.dt})

        # record rates and connect neurons
        self.neurons = self.rate_neuron_1 + \
            self.rate_neuron_2 + self.rate_neuron_3

        nest.Connect(
            self.multimeter, self.neurons, 'all_to_all', {'delay': 10.})

        nest.Connect(self.rate_neuron_drive, self.rate_neuron_1,
                     'all_to_all', {'model': 'rate_connection_delayed',
                                    'delay': self.delay,
                                    'weight': self.weight})

        nest.Connect(self.rate_neuron_drive, self.rate_neuron_2,
                     'all_to_all', {'model': 'rate_connection_instantaneous',
                                    'weight': self.weight})

        nest.Connect(self.rate_neuron_drive, self.rate_neuron_3,
                     'all_to_all', {'model': 'rate_connection_instantaneous',
                                    'weight': self.weight})

    def test_RateNeuronDelay(self):
        """Check the delay of the connection"""

        # simulate
        nest.Simulate(self.simtime)

        # get noise from rate neuron
        events = nest.GetStatus(self.multimeter)[0]["events"]
        senders = events['senders']
        times = events['times'][np.where(senders == self.rate_neuron_1.get('global_id'))]
        rate_1 = events['rate'][np.where(senders == self.rate_neuron_1.get('global_id'))]
        rate_2 = events['rate'][np.where(senders == self.rate_neuron_2.get('global_id'))]

        delay_rate_1 = times[np.where(rate_1 > 0)[0][0]]
        test_delay_1 = self.delay + self.dt
        self.assertTrue(np.isclose(delay_rate_1, test_delay_1))
        self.assertTrue(rate_2[0] > 0.)

    def test_RateNeuronWeight(self):
        """Check the weight of the connection"""

        # simulate
        nest.Simulate(self.simtime)

        # get noise from rate neuron
        events = nest.GetStatus(self.multimeter)[0]["events"]
        senders = events['senders']
        rate_1 = events['rate'][np.where(senders == self.rate_neuron_1.get('global_id'))]

        value = rate_1[-1]
        value_test = self.drive * self.weight
        self.assertTrue(np.isclose(value, value_test))

    def test_RateNeuronNL(self):
        """Check the non-linearity of the neuron"""

        gs = [1., 2.]
        lin_sums = [True, False]

        for g, ls in zip(gs, lin_sums):

            nest.SetStatus(self.neurons, {'g': g, 'linear_summation': ls})

            # simulate
            nest.Simulate(self.simtime)

            # get noise from rate neuron
            events = nest.GetStatus(self.multimeter)[0]["events"]
            senders = events['senders']
            rate_1 = events['rate'][
                np.where(senders == self.rate_neuron_1.get('global_id'))][-1]
            rate_2 = events['rate'][
                np.where(senders == self.rate_neuron_2.get('global_id'))][-1]
            rate_3 = events['rate'][
                np.where(senders == self.rate_neuron_3.get('global_id'))][-1]

            rates = np.array([rate_1, rate_2, rate_3])

            if ls:
                rates_test = np.array(
                    [g * self.drive * self.weight,
                     np.tanh(g * self.drive * self.weight),
                     g * self.drive * self.weight * H(self.drive *
                                                      self.weight)])
            else:
                rates_test = np.array(
                    [g * self.drive * self.weight,
                     self.weight * np.tanh(g * self.drive),
                     self.weight * self.drive * g * H(self.drive)])

            self.assertTrue(np.allclose(rates, rates_test))


def suite():

    # makeSuite is sort of obsolete http://bugs.python.org/issue2721
    # using loadTestsFromTestCase instead.
    suite1 = unittest.TestLoader().loadTestsFromTestCase(
        RateNeuronCommunicationTestCase)
    return unittest.TestSuite([suite1])


def run():
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())


if __name__ == "__main__":
    run()
