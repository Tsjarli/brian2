'''
Some basic tests for the `Variable` system
'''
from collections import namedtuple
import numpy as np
from numpy.testing import assert_raises

from brian2.core.variables import *
from brian2.units.fundamentalunits import Unit
from brian2.units.allunits import second


def test_construction_errors():
    # Mismatching dtype information
    assert_raises(TypeError, lambda: Variable(Unit(1), owner=None,
                                              value=np.arange(10),
                                              dtype=np.float32,
                                              device=None))
    # Boolean variable that isn't dimensionless
    assert_raises(ValueError, lambda: Variable(second, owner=None,
                                               is_bool=True, device=None))

    # Dynamic array variable that is constant but not constant in size
    assert_raises(ValueError, lambda: DynamicArrayVariable(Unit(1),
                                                           owner=None,
                                                           name='name',
                                                           size=0,
                                                           device=None,
                                                           constant=True,
                                                           constant_size=False))


def test_str_repr():
    # Basic test that the str/repr methods work
    FakeGroup = namedtuple('G', ['name'])
    group = FakeGroup(name='groupname')
    variables = [Variable(second, owner=None, device=None),
                 AuxiliaryVariable(second),
                 AttributeVariable(second, group, 'name', dtype=np.float32),
                 ArrayVariable(second, owner=None, name='name', size=10, device=None),
                 DynamicArrayVariable(second, owner=None, name='name', size=0,
                                      device=None),
                 Subexpression('sub', second, expr='a+b', owner=group)]
    for var in variables:
        assert len(str(var))
        # The repr value should contain the name of the class
        assert len(repr(var)) and var.__class__.__name__ in repr(var)


if __name__ == '__main__':
    test_construction_errors()
    test_str_repr()
