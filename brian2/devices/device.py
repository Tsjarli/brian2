'''
Module containing the `Device` base class as well as the `RuntimeDevice`
implementation and some helper functions to access/set devices.
'''

import numpy as np

from brian2.memory.dynamicarray import DynamicArray, DynamicArray1D
from brian2.codegen.targets import codegen_targets
from brian2.codegen.functions import add_numpy_implementation
from brian2.codegen.runtime.numpy_rt import NumpyCodeObject
from brian2.codegen.translation import translate
from brian2.core.names import find_name
from brian2.core.preferences import brian_prefs
from brian2.core.variables import ArrayVariable, DynamicArrayVariable
from brian2.core.functions import Function
from brian2.units.fundamentalunits import Unit
from brian2.utils.logger import get_logger

__all__ = ['Device', 'RuntimeDevice',
           'get_device', 'set_device',
           'all_devices',
           'insert_device_code',
           ]

logger = get_logger(__name__)

all_devices = {}


def get_default_codeobject_class():
    '''
    Returns the default `CodeObject` class from the preferences.
    '''
    codeobj_class = brian_prefs['codegen.target']
    if isinstance(codeobj_class, str):
        for target in codegen_targets:
            if target.class_name == codeobj_class:
                return target
        # No target found
        raise ValueError("Unknown code generation target: %s, should be "
                         " one of %s"%(codeobj_class,
                                       [target.class_name
                                        for target in codegen_targets]))
    return codeobj_class


class Device(object):
    '''
    Base Device object.
    '''
    def __init__(self):
        pass

    def get_array_name(self, var, access_data=True):
        '''
        Return a globally unique name for `var`.

        Parameters
        ----------
        access_data : bool, optional
            For `DynamicArrayVariable` objects, specifying `True` here means the
            name for the underlying data is returned. If specifying `False`,
            the name of object itself is returned (e.g. to allow resizing).
        '''
        raise NotImplementedError()

    def add_variable(self, var):
        raise NotImplementedError()

    def init_with_zeros(self, var):
        raise NotImplementedError()

    def init_with_arange(self, var, start):
        raise NotImplementedError()

    def fill_with_array(self, var, arr):
        raise NotImplementedError()

    def spike_queue(self, source_start, source_end):
        '''
        Create and return a new `SpikeQueue` for this `Device`.

        Parameters
        ----------
        source_start : int
            The start index of the source group (necessary for subgroups)
        source_end : int
            The end index of the source group (necessary for subgroups)
        '''
        raise NotImplementedError()

    def code_object_class(self, codeobj_class=None):
        if codeobj_class is None:
            codeobj_class = get_default_codeobject_class()
        return codeobj_class

    def code_object(self, owner, name, abstract_code, variables, template_name,
                    variable_indices, codeobj_class=None,
                    template_kwds=None):
        codeobj_class = self.code_object_class(codeobj_class)
        language = codeobj_class.language

        if template_kwds is None:
            template_kwds = dict()
        else:
            template_kwds = template_kwds.copy()

        template = getattr(codeobj_class.templater, template_name)

        # Check that all functions are available
        for varname, value in variables.iteritems():
            if isinstance(value, Function):
                try:
                    value.implementations[codeobj_class]
                except KeyError as ex:
                    # if we are dealing with numpy, add the default implementation
                    if codeobj_class is NumpyCodeObject:
                        add_numpy_implementation(value, value.pyfunc)
                    else:
                        raise NotImplementedError(('Cannot use function '
                                                   '%s: %s') % (varname, ex))

        if isinstance(abstract_code, dict):
            for k, v in abstract_code.items():
                logger.debug('%s abstract code key %s:\n%s' % (name, k, v))
        else:
            logger.debug(name + " abstract code:\n" + abstract_code)
        iterate_all = template.iterate_all
        snippet, kwds = translate(abstract_code, variables,
                                  dtype=brian_prefs['core.default_scalar_dtype'],
                                  codeobj_class=codeobj_class,
                                  variable_indices=variable_indices,
                                  iterate_all=iterate_all)
        # Add the array names as keywords as well
        for varname, var in variables.iteritems():
            if isinstance(var, ArrayVariable):
                pointer_name = language.get_array_name(var)
                template_kwds[varname] = pointer_name
                if hasattr(var, 'resize'):
                    dyn_array_name = language.get_array_name(var,
                                                             access_data=False)
                    template_kwds['_object_'+varname] = dyn_array_name


        template_kwds.update(kwds)
        logger.debug(name + " snippet:\n" + str(snippet))

        name = find_name(name)

        code = template(snippet,
                        owner=owner, variables=variables, codeobj_name=name,
                        variable_indices=variable_indices,
                        get_array_name=language.get_array_name,
                        **template_kwds)
        logger.debug(name + " code:\n" + str(code))

        codeobj = codeobj_class(owner, code, variables, name=name)
        codeobj.compile()
        return codeobj
    
    def activate(self):
        '''
        Called when this device is set as the current device.
        '''
        pass

    def insert_device_code(self, slot, code):
        '''
        Insert code directly into a given slot in the device. By default does nothing.
        '''
        logger.warn("Ignoring device code, unknown slot: %s, code: %s" % (slot, code))
    
    
class RuntimeDevice(Device):
    '''
    '''
    def __init__(self):
        super(Device, self).__init__()
        #: Mapping from `Variable` objects to numpy arrays (or `DynamicArray`
        #: objects)
        self.arrays = {}

    def get_array_name(self, var, access_data=True):
        # if no owner is set, this is a temporary object (e.g. the array
        # of indices when doing G.x[indices] = ...). The name is not
        # necessarily unique over several CodeObjects in this case.
        owner_name = getattr(var.owner, 'name', 'temporary')

        if isinstance(var, DynamicArrayVariable):
            if access_data:
                return '_array_' + owner_name + '_' + var.name
            else:
                return '_dynamic_array_' + owner_name + '_' + var.name
        elif isinstance(var, ArrayVariable):
            return '_array_' + owner_name + '_' + var.name
        else:
            raise TypeError(('Do not have a name for variable of type '
                             '%s') % type(var))

    def add_variable(self, var):
        # This creates the actual numpy arrays (or DynamicArrayVariable objects)
        arr = None
        if isinstance(var, DynamicArrayVariable):
            if var.dimensions == 1:
                arr = DynamicArray1D(var.size, dtype=var.dtype)
            else:
                arr = DynamicArray(var.size, dtype=var.dtype)
        elif isinstance(var, ArrayVariable):
            arr = np.empty(var.size, dtype=var.dtype)

        if arr is not None:
            self.arrays[var] = arr

    def get_value(self, var, access_data=True):
        if isinstance(var, DynamicArrayVariable) and access_data:
                return self.arrays[var].data
        else:
            return self.arrays[var]

    def set_value(self, var, value):
        self.arrays[var][:] = value

    def resize(self, var, new_size):
        self.arrays[var].resize(new_size)

    def init_with_zeros(self, var):
        self.arrays[var][:] = 0

    def init_with_arange(self, var, start):
        self.arrays[var][:] = np.arange(start, stop=var.size+start)

    def fill_with_array(self, var, arr):
        self.arrays[var][:] = arr

    def spike_queue(self, source_start, source_end):
        # Use the C++ version of the SpikeQueue when available
        try:
            from brian2.synapses.cythonspikequeue import SpikeQueue
            logger.info('Using the C++ SpikeQueue', once=True)
        except ImportError:
            from brian2.synapses.spikequeue import SpikeQueue
            logger.info('Using the Python SpikeQueue', once=True)

        return SpikeQueue(source_start=source_start, source_end=source_end)


runtime_device = RuntimeDevice()

all_devices['runtime'] = runtime_device

current_device = runtime_device

def get_device():
    '''
    Gets the current `Device` object
    '''
    global current_device
    return current_device

def set_device(device):
    '''
    Sets the current `Device` object
    '''
    global current_device
    if isinstance(device, str):
        device = all_devices[device]
    current_device = device
    current_device.activate()


def insert_device_code(slot, code):
    '''
    Inserts the given set of code into the slot defined by the device.
    
    The behaviour of this function is device dependent. The runtime device ignores it (useful for debugging).
    '''
    get_device().insert_device_code(slot, code)
