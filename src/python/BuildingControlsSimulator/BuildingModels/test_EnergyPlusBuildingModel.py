#!/usr/bin/env python
# created by Tom Stesco tom.s@ecobee.com

import subprocess
import os
import shutil
import logging

import pytest
import pyfmi
import numpy as np

from BuildingControlsSimulator.BuildingModels.IDFPreprocessor import (
    IDFPreprocessor,
)
from BuildingControlsSimulator.BuildingModels.EnergyPlusBuildingModel import (
    EnergyPlusBuildingModel,
)


logger = logging.getLogger(__name__)


class TestEnergyPlusBuildingModel:
    @classmethod
    def setup_class(cls):
        # basic IDF file found in all EnergyPlus installations
        cls.dummy_idf_name = "Furnace.idf"

        cls.dummy_epw_name = "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"

        # if dummy files don't exist copy them from E+ installations
        cls.dummy_epw_path = os.path.join(
            os.environ.get("WEATHER_DIR"), cls.dummy_epw_name
        )
        if not os.path.isfile(cls.dummy_epw_path):
            _fpath = os.path.join(
                os.environ.get("EPLUS_DIR"), "WeatherData", cls.dummy_epw_name,
            )
            shutil.copyfile(_fpath, cls.dummy_epw_path)

        # if dummy files don't exist copy them from E+ installations
        cls.dummy_idf_path = os.path.join(
            os.environ.get("IDF_DIR"), cls.dummy_idf_name
        )
        if not os.path.isfile(cls.dummy_idf_path):
            _fpath = os.path.join(
                os.environ.get("EPLUS_DIR"), "ExampleFiles", cls.dummy_idf_name
            )
            shutil.copyfile(_fpath, cls.dummy_idf_path)

        # make test/ dirs
        EnergyPlusBuildingModel.make_directories()
        cls.building_model = EnergyPlusBuildingModel(
            idf=IDFPreprocessor(
                idf_file=cls.dummy_idf_path, init_temperature=20.0,
            ),
            epw_path=cls.dummy_epw_path,
            timesteps_per_hour=12,
        )

        cls.step_size = int(3600.0 / cls.building_model.timesteps_per_hour)

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a call to
        setup_class.
        """
        pass

    def test_energyplus_accessible(self):
        """test that energyplus version is test version and is accessible"""
        cmd = "energyplus -v"
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        assert out.stdout == "EnergyPlus, Version 8.9.0-40101eaafd\n"

    def test_preprocess(self):
        """test that preprocessing produces output file"""
        prep_idf = self.building_model.idf.preprocess(preprocess_check=False)
        assert os.path.exists(prep_idf)

        # test that preprocessing produces valid IDF output file
        assert self.building_model.idf.check_valid_idf(prep_idf) is True

    def test_make_fmu(self):
        """test that make_fmu produces fmu file"""
        fmu = self.building_model.create_model_fmu(
            epw_path=self.building_model.epw_path, preprocess_check=False
        )
        assert os.path.exists(fmu)

    def test_fmu_compliance(self):
        """test that fmu file is compliant with FMI.
        
        Note: if this test fails check ./Output_EPExport_Slave/Furnace_prep.err
        """
        output_path = os.path.join(
            os.environ.get("OUTPUT_DIR"), "compliance_check_output.csv"
        )
        # use `bash expect` to run non-interactive
        cmd = (
            "expect 'Press enter to continue.' {{ send '\r' }} |"
            f' {os.environ.get("EXT_DIR")}/FMUComplianceChecker/fmuCheck.linux64'
            f" -h {self.step_size}"
            " -s 172800"
            f" -o {output_path} {self.building_model.fmu_path}"
        )
        logger.info("FMU compliance checker command:")
        logger.info(cmd)
        # shlex causes FMUComplianceChecker to run with options, use cmd string
        out = subprocess.run(
            cmd, shell=True, capture_output=False, text=True, input="\n"
        )

        assert out.returncode == 0

    def test_pyfmi_load_fmu(self):
        """test that fmu can be loaded with pyfmi"""
        fmu = pyfmi.load_fmu(self.building_model.fmu_path)
        assert fmu.get_version() == "1.0"

    def test_simulate_fmu(self):
        """test that fmu can be simulated with pyfmi
        
        Note: if this test fails check ./Output_EPExport_Slave/Furnace_prep.err
        """
        fmu = pyfmi.load_fmu(self.building_model.fmu_path)
        opts = fmu.simulate_options()
        t_end = 86400.0
        opts["ncp"] = int(t_end / self.step_size)

        res = fmu.simulate(final_time=t_end, options=opts)

        output = res.result_data.get_data_matrix()

        assert output.shape == (30, opts["ncp"] + 1)

    # note: this test is redundant to next test that uses the full
    # EnergyPlusBuildingModel class
    @pytest.mark.skip(
        reason="Segfaults when run without PDB breakpoint. Tried fmu.free_instance(), fmu.terminate()"
    )
    def test_step_fmu(self):
        """test that fmu can be simulated with pyfmi
        
        Note: if this test fails check ./Output_EPExport_Slave/Furnace_prep.err
        """
        fmu = pyfmi.load_fmu(self.building_model.fmu_path)
        t_start = 0
        t_end = 86400.0
        t_step = 300.0
        ns = int(t_end / t_step)

        fmu.initialize(t_start, t_end)
        status = np.full(ns, False, dtype="int8")

        for i in range(ns):
            status[i] = fmu.do_step(
                current_t=t_start, step_size=t_step, new_step=True,
            )
            t_start += t_step
        logger.info(f"status={all(status == 0)}")

        # fmu.free_instance()
        # status == 0 corresponds to `fmi1_status_ok`
        # see: https://github.com/modelon-community/PyFMI/blob/PyFMI-2.7.4/src/pyfmi/fmil_import.pxd
        assert all(status == 0)

    def test_step_model(self):
        """test that fmu can be simulated with pyfmi
        
        Note: if this test fails check ./Output_EPExport_Slave/Furnace_prep.err
        """
        t_start = 0
        t_end = 86400.0
        t_step = 300.0
        ns = int(t_end / t_step)

        self.building_model.create_model_fmu(
            epw_path=self.building_model.epw_path, preprocess_check=False
        )

        self.building_model.initialize(
            t_start=t_start, t_end=t_end, t_step=t_step
        )

        step_control_input = {
            "heat_stage_one": True,
            "heat_stage_two": False,
            "heat_stage_three": False,
            "compressor_cool_stage_one": False,
            "compressor_cool_stage_two": False,
            "compressore_cool_stage_one": False,
            "compressor_cool_stage_three": False,
            "fan_stage_one": False,
            "fan_stage_two": False,
            "fan_stage_three": False,
        }
        for i in range(ns):
            self.building_model.do_step(
                t_start=self.building_model.output[STATES.SIMULATION_TIME][i],
                t_step=300,
                step_control_input=step_control_input,
                step_weather_input={},
                step_occupancy_input={},
            )
        assert (
            pytest.approx(33.394825, 0.01)
            == self.building_model.fmu_output[
                "EAST_ZONE_zone_air_temperature"
            ].mean()
        )
