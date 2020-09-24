# created by Tom Stesco tom.s@ecobee.com

import os
import abc
from enum import IntEnum
import logging

import attr
import pandas as pd
import numpy as np
from eppy import modeleditor


class HVAC_modes(IntEnum):
    """
    0 - Uncontrolled (No specification or default)
    1 - Single Heating Setpoint
    2 - Single Cooling SetPoint
    3 - Single Heating Cooling Setpoint
    4 - Dual Setpoint with Deadband (Heating and Cooling)
    """

    UNCONTROLLED = 0
    SINGLE_HEATING_SETPOINT = 1
    SINGLE_COOLING_SETPOINT = 2
    DUAL_HEATING_COOLING_SETPOINT = 3


@attr.s
class ControlModel(object):
    """ABC for control models

    Example:
    ```python
    src.IDFPreprocessor.()
    ```
    
    """

    def initialize(self, start_time_seconds, final_time_seconds):
        """
        """
        pass

    def do_step(self):
        """
        """
        pass

    # FMU_control_cooling_stp_name = attr.ib(kw_only=True)
    # FMU_control_heating_stp_name = attr.ib(kw_only=True)
    # FMU_control_type_name = attr.ib(kw_only=True)
    # def __init__(self,
    #     FMU_control_heating_stp_name,
    #     FMU_control_cooling_stp_name,
    #     FMU_control_type_name):
    # """
    # """
    #     self.allowed_keys = [
    #         "FMU_control_cooling_stp_name",
    #         "FMU_control_heating_stp_name",
    #         "FMU_control_type_name"
    #     ]
    #     for key, value in kwargs.items():
    #         if key in allowed_keys:
    #             setattr(self, key, value)
