# created by Tom Stesco tom.s@ecobee.com

import attr
import pandas as pd
import numpy as np

from BuildingControlsSimulator.ControlModels.ControlModel import ControlModel
from BuildingControlsSimulator.DataClients.DataStates import STATES
from BuildingControlsSimulator.DataClients.DataSpec import Internal
from BuildingControlsSimulator.Conversions.Conversions import Conversions


@attr.s
class Deadband(ControlModel):
    """Deadband controller"""

    deadband = attr.ib(default=1.0)
    step_output = attr.ib(factory=dict)
    step_size_seconds = attr.ib(default=None)
    current_t_idx = attr.ib(default=None)

    output = attr.ib(factory=dict)

    # for reference on how attr defaults wor for mutable types (e.g. list) see:
    # https://www.attrs.org/en/stable/init.html#defaults
    input_states = attr.ib()
    output_states = attr.ib()

    @input_states.default
    def get_input_states(self):
        return [
            STATES.THERMOSTAT_TEMPERATURE,
            STATES.TEMPERATURE_STP_COOL,
            STATES.TEMPERATURE_STP_HEAT,
        ]

    @output_states.default
    def get_output_states(self):
        return [
            STATES.TEMPERATURE_CTRL,
            STATES.AUXHEAT1,
            STATES.AUXHEAT2,
            STATES.AUXHEAT3,
            STATES.COMPCOOL1,
            STATES.COMPCOOL2,
            STATES.COMPHEAT1,
            STATES.COMPHEAT2,
            STATES.FAN_STAGE_ONE,
            STATES.FAN_STAGE_TWO,
            STATES.FAN_STAGE_THREE,
        ]

    def initialize(self, t_start, t_end, t_step, categories_dict):
        """
        """
        self.current_t_idx = 0
        self.step_size_seconds = t_step
        self.allocate_output_memory(
            t_start=t_start,
            t_end=t_end,
            t_step=t_step,
            categories_dict=categories_dict,
        )
        self.init_step_output()

    def allocate_output_memory(self, t_start, t_end, t_step, categories_dict):
        """preallocate output memory to speed up simulation"""
        # reset output
        self.output = {}

        self.output = {
            STATES.SIMULATION_TIME: np.arange(
                t_start, t_end + t_step, t_step, dtype="int64"
            )
        }
        n_s = len(self.output[STATES.SIMULATION_TIME])

        # add state variables
        for state in self.output_states:
            if Internal.full.spec[state]["dtype"] == "category":
                self.output[state] = pd.Series(
                    pd.Categorical(
                        pd.Series(index=np.arange(n_s)),
                        categories=categories_dict[state],
                    )
                )
            else:
                (
                    np_default_value,
                    np_dtype,
                ) = Conversions.numpy_down_cast_default_value_dtype(
                    Internal.full.spec[state]["dtype"]
                )
                self.output[state] = np.full(
                    n_s, np_default_value, dtype=np_dtype,
                )

        self.output[STATES.STEP_STATUS] = np.full(n_s, 0, dtype="int8")

    def tear_down(self):
        """tear down FMU"""
        pass

    def init_step_output(self):
        # initialize all off
        self.step_output = {state: 0 for state in self.output_states}

    def do_step(
        self,
        t_start,
        t_step,
        step_hvac_input,
        step_sensor_input,
        step_weather_input,
    ):
        """Simulate controller time step."""
        t_ctrl = step_sensor_input[STATES.THERMOSTAT_TEMPERATURE]
        self.step_output[STATES.TEMPERATURE_CTRL] = t_ctrl

        if t_ctrl < (
            step_hvac_input[STATES.TEMPERATURE_STP_HEAT] - self.deadband
        ):
            # turn on heat
            # turn off cool
            self.step_output[STATES.AUXHEAT1] = self.step_size_seconds
            self.step_output[STATES.FAN_STAGE_ONE] = self.step_size_seconds
            self.step_output[STATES.COMPCOOL1] = 0
        elif t_ctrl > (
            step_hvac_input[STATES.TEMPERATURE_STP_COOL] + self.deadband
        ):
            # turn on cool
            # turn off heat
            self.step_output[STATES.COMPCOOL1] = self.step_size_seconds
            self.step_output[STATES.FAN_STAGE_ONE] = self.step_size_seconds
            self.step_output[STATES.AUXHEAT1] = 0
        else:
            # turn off heat
            # turn off cool
            self.step_output[STATES.AUXHEAT1] = 0
            self.step_output[STATES.COMPCOOL1] = 0
            self.step_output[STATES.FAN_STAGE_ONE] = 0

        self.add_step_to_output(self.step_output)
        self.current_t_idx += 1

        return self.step_output

    def add_step_to_output(self, step_output):
        for k, v in step_output.items():
            self.output[k][self.current_t_idx] = v
