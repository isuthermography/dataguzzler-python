import numpy as np
import pint 

class AxisBase:
    """Base class for a motion controller axis providing attributes
    and properties and methods you should override"""
    axis_name = None # Name of this axis within its controller as a python string
    unit_name=None # String representing axis default units
    unit_quantity=None # Pint quantity corresponding to axis default units
    parent = None # Motion controller that contains this axis


    def wait(self):
        """Wait for this axis to stop moving."""
        self.parent.wait([self.axis_name])
        pass

    @property
    def waitrel(self):
        """On read, returns None; on assignment, initiates a move
        relative to the current position and waits for the move to
        complete. Position can be a number, which is assumed to be in
        the axis default units, or a Pint quantity."""
        return None

    @waitrel.setter
    def waitrel(self, value):
        # Value may be given as just a number, in which case
        # default units are assumed, or as a pint quantity.
        self.rel = value
        self.wait()
        pass

    @property
    def waitpos(self):
        """On read, returns the current axis position; on assignment
        initiates the move to the specified position and waits for the
        move to complete. Position can be a number, which is assumed
        to be in the axis default units, or a Pint quantity."""
        return self.pos

    @waitpos.setter
    def waitpos(self, value):
        # Value may be given as just a number, in which case
        # default units are assumed, or as a pint quantity.
        self.pos = value
        self.wait()
        pass
    
    def zero(self):
        """This method zeros the axis, defining the current position to be 0.0"""
        raise NotImplementedError

    def moving(self):
        """Returns True if the axis is moving or False if it is stopped"""
        raise NotImplementedError

    @property
    def rel(self):
        """On read, returns None; on assignment, initiates a move
        relative to the current position. Position can be a number,
        which is assumed to be in the axis default units, or a Pint
        quantity."""
        return None

    @rel.setter
    def rel(self, value):
        # Must be implemented by subclass
        # Value may be given as just a number, in which case
        # default units are assumed, or as a pint quantity.
        raise NotImplementedError

    def cancel(self):
        """Cancel any move in progress on this axis"""
        raise NotImplementedError

    @property
    def pos(self):
        """On read, returns the current axis position;
        on assignment initiates the move to the specified
        position. Position can be a number, which is assumed
        to be in the axis default units, or a Pint quantity."""
        raise NotImplementedError

    @pos.setter
    def pos(self, value):
        # Must be implemented by subclass
        # Value may be given as just a number, in which case
        # default units are assumed, or as a pint quantity.
        raise NotImplementedError

    @property
    def enabled(self):
        """On read, returns True if the current axis is enabled, False
        otherwise. On assignment, attempts to turn the axis on or off
        according to the truth value provided (True or False)."""
        raise NotImplementedError

    @enabled.setter
    def enabled(self, value):
        raise NotImplementedError
    
    pass

class SimpleAxisGroup:
    """Simple implementation of a group of axes that behaves similarly
    to a single axis. Intended so that it can be subclassed when
    special functionality is needed."""
    
    axis_names=None # List of axis names
    parent=None # Motion controller object
    unit_names = None # List or array of names of axis default units
    unit_quantities = None # List of axis default unit quantities 
    matching_units=None # True if all axes use exactly the same units
    
    def __init__(self, parent, axis_names):
        self.parent = parent
        self.axis_names = axis_names
        self.unit_names = []
        self.unit_quantities = []

        self.matching_units = True
        axis0_quantity = self.parent.axis[axis_names[0]].unit_quantity
        for axis_num in range(1, len(self.axis_names)):
            axis_name = axis_names[axis_num]
            if self.parent.axis[axis_name].unit_quantity != axis0_quantity:
                self.matching_units = False
                pass
            pass
        pass

    def wait(self):
        """Wait for all axes in the group to stop moving"""
        self.parent.wait(self.axis_names)
        pass

    @property
    def waitrel(self):
        """On read, returns None; on assignment, initiates a move
        relative to the current position and waits for the move to
        complete. Position can be an iterable of numbers, which are
        assumed to be in the axis default units, or Pint quantities.

        """
        return None

    @waitrel.setter
    def waitrel(self, value):
        # Value may be given as just numbers, in which case
        # default units are assumed, or as pint quantities.
        self.rel = value
        self.wait()
        pass

    @property
    def waitpos(self):
        """On read, returns the current axis positions; on assignment
        initiates the move to the specified position and waits for the
        move to complete. Position can be an iterable of numbers,
        which are assumed to be in the axis default units, or Pint
        quantities.

        """
        return self.pos

    @waitpos.setter
    def waitpos(self, value):
        # Value may be given as just numbers, in which case
        # default units are assumed, or as pint quantities.
        self.pos = value
        self.wait()
        pass
    
    def zero(self):
        """This method zeros all the axes, defining the current
        position to be 0.0"""
        for axis_name in self.axis_names:
            axis = self.parent.axis[axis_name]
            axis.zero()
            pass
        pass


    @property
    def moving(self):
        """Returns an array of Trues for axes that are moving and
        Falses for axes that are stopped"""
        moving = np.zeros(len(self.axis_names), dtype=bool)
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = self.parent.axis[axis_name]
            moving[axis_num] = axis.moving
            pass
        return moving

    @property
    def rel(self):
        """On read, returns None; on assignment, initiates a move
        relative to the current position. Position can be an iterable
        of numbers, which are assumed to be in the axis default units,
        or Pint quantities.

        """
        return None

    @rel.setter
    def rel(self, value):
        if len(value) != len(self.axis_names):
            raise ValueError("Incorrect number of axis offsets given")
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = self.parent.axis[axis_name]
            desired_rel = value[axis_num]
            if desired_rel is not None and not np.isnan(desired_rel):
                axis.rel=desired_rel
                pass
            pass
        pass

    def cancel(self):
        """Cancel any move in progress on all axes in this group"""
        for axis_name in self.axis_names:
            axis = self.parent.axis[axis_name]
            axis.cancel()
            pass
        pass

    @property
    def pos(self):
        """On read, returns the current axis positions; on assignment
        initiates the move to the specified position. Position can be
        an iterable of numbers, which are assumed to be in the axis
        default units, or Pint quantities.

        """
        ur = pint.get_application_registry()
        if self.matching_units:
            # Create a single numpy quantity with the correct units
            pos = ur.Quantity(np.zeros(len(self.axis_names), dtype='d'), self.parent[self.axis_names[0]].unit_quantity)
            pass
        else:
            # Create a numpy array of objects which are scalar quantities
            pos = np.zeros(len(self.axis_names), dtype=object)
            pass
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = self.parent.axis[axis_name]
            pos[axis_num] = axis.pos
            pass
        return pos

    @pos.setter
    def pos(self, value):
        if len(value) != len(self.axis_names):
            raise ValueError("Incorrect number of axis offsets given")
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = self.parent.axis[axis_name]
            desired_pos = value[axis_num]
            if desired_pos is not None and not np.isnan(desired_pos):
                
                axis.pos = desired_pos
                pass
            pass
        pass

    @property
    def enabled(self):
        """On read, returns a boolean array that is true for axes that
        are enabled, and False otherwise. On assignment, attempts to
        turn the given axes on or off according to the truth value
        provided (True or False).

        """
        enabled = np.zeros(len(self.axis_names), dtype=bool)
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = self.parent.axis[axis_name]
            enabled[axis_num] = axis.enabled
            pass
        return enabled

    @enabled.setter
    def enabled(self, value):
        if isinstance(value, bool):
            for axis_name in self.axis_names:
                axis = self.parent.axis[axis_name]
                axis.enabled = value
                pass
            return
        if len(value) != len(self.axis_names):
            raise ValueError("Incorrect number of axis offsets given")
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = self.parent.axis[axis_name]
            axis.enabled = value[axis_num]
            pass
        pass
    pass

class MotionControllerBase:
    """Base class for motion controllers providing attributes and
    properties and methods you should override. Don't forget to
    also use the dgpy.Module metaclass"""

    axis=None # Ordered dictionary of axis objects
    all=None # axis_group object representing all axes

    # In addition each defined axis should be referenced
    # by an attribute of the same name
    
    @property
    def axes(self):
        """Returns a list or array of axis names"""
        return list(self.axis.keys())

    @property
    def axis_unit_names(self):
        """Returns a list or array of axis unit names"""
        return [self.axis[axis_name.unit_name] for axis_name in self.axis ]

    @property
    def axis_unit_quantities(self):
        """Returns a list or array of axis units (pint quantity)"""
        return [self.axis[axis_name.unit_quantity] for axis_name in self.axis ]

    def create_group(self,axis_name_list):
        """Create and return an axis group (instance or subclass of
        SimpleAxisGroup) based on the given list of axis names"""
        # Override this method if you have a custom group class
        # for your motion controller. 
        return SimpleAxisGroup(self,axis_name_list)
    
    def wait(self,axis_name_list):
        """Waits for each axis named in the given list to stop moving"""
        raise NotImplementedError
    
    pass
