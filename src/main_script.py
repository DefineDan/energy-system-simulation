"""
Created on Thu Jan  9 11:29:34 2020

@author: Daniel
"""

# Default logger of oemof
from oemof.tools import logger
from oemof.tools import helpers

import oemof.solph as solph
import oemof.outputlib as outputlib

import logging
import os
import pandas as pd
from basic_analysis import display_results
from basic_analysis import plot_results_elec
from basic_analysis import plot_results_heat
from basic_analysis import plot_results_ressources

###############################################################################
# definition of config file locally
###############################################################################
cfg = {}
cfg['design_parameters_file_name'] = 'design_parameters.csv'
cfg['parameters_file_name'] = 'general_parameters.csv'
cfg['time_series_file_name'] = 'weather_data.csv'

cfg['debug'] = False
cfg['display_input_data'] = True
cfg['display_results'] = True
cfg['solver'] = 'cbc'
cfg['solver_verbose'] = False


###############################################################################
# run model
###############################################################################

# initiate the logger (see the API docs for more information)
logger.define_logging(logfile='model.log', screen_level=logging.INFO,
                      file_level=logging.DEBUG)
logging.info('Initialize the energy system')

if cfg['debug']:
    number_of_time_steps = 3
else:
    number_of_time_steps = 8760
    
date_time_index = pd.date_range('1/1/2030', periods=number_of_time_steps, freq='H')
energysystem = solph.EnergySystem(timeindex=date_time_index)


##########################################################################
# Read time series and parameter values from data files
##########################################################################

abs_path = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))

file_path_ts = abs_path + '/data/' + cfg['time_series_file_name']
data = pd.read_csv(file_path_ts)

# file_path_weather_ts = abs_path + '/data_preprocessed/' + cfg[
#     'weather_time_series']
# weather_data = pd.read_csv(file_path_weather_ts)

file_name_param_01 = cfg['design_parameters_file_name']
file_name_param_02 = cfg['parameters_file_name']
file_path_param_01 = (abs_path + '/data/' + file_name_param_01)
file_path_param_02 = (abs_path + '/data/' + file_name_param_02)

param_df_01 = pd.read_csv(file_path_param_01, index_col=1)
param_df_02 = pd.read_csv(file_path_param_02, index_col=1)

param_df = pd.concat([param_df_01, param_df_02], sort=True)
param_value = param_df['value']


##########################################################################
# Create oemof object
##########################################################################

logging.info('Create oemof objects')

## Bus objects
###############################################################################
bgas = solph.Bus(label="natural_gas")
bel = solph.Bus(label="electricity")
bth = solph.Bus(label='heat')

energysystem.add(bgas, bel, bth)

## Sink objects
###############################################################################
#Electricty demand
energysystem.add(
        solph.Sink(label='demand_el',
                   inputs={bel: solph.Flow(
                           actual_value=data['Demand_el [MWh]'],  # [MWh]
                           nominal_value=1,
                           fixed=True)})
                )

#Heat demand
energysystem.add(
        solph.Sink(label='demand_th',
                   inputs={bth: solph.Flow(
                           actual_value=data['Demand_th [MWh]'],  # [MWh]
                           nominal_value=1,
                           fixed=True)})
                )

#Excell electricity    
energysystem.add(
        solph.Sink(label='excess_bel',
                   inputs={bel: solph.Flow(
                           variable_costs=param_value['var_costs_excess_bel'])})
                )

#Excess heat
energysystem.add(
        solph.Sink(label='excess_bth',
                   inputs={bth: solph.Flow(
                           variable_costs=param_value['var_costs_excess_bth'])})
                )


## Source objects
###############################################################################
#Electricty shortage    
energysystem.add(
        solph.Source(label='shortage_bel',
                     outputs={bel: solph.Flow(
                             variable_costs=param_value['var_costs_shortage_bel'])})
                )

#Heat shortage    
energysystem.add(
        solph.Source(label='shortage_bth',
                     outputs={bth: solph.Flow(
                             variable_costs=param_value['var_costs_shortage_bth'])})
                )

#Natural gas    
energysystem.add(
        solph.Source(label='rgas',
                     outputs={bgas: solph.Flow(
                             nominal_value=param_value['nom_val_gas'],
                             summed_max=param_value['sum_max_gas'],
                             variable_costs=param_value['var_costs_gas'])})
                )
   
# Wind turbines
if param_value['number_of_windturbines'] > 0:    
    energysystem.add(           
            solph.Source(label='wind_turbine',
                         outputs={bel: solph.Flow(
                                 actual_value=(data['Wind_power [kW/unit]'] * param_value['number_of_windturbines'] * 0.001),  # [MWh]
                                 nominal_value=1, # [1]
                                 fixed=True)})
                    )
            
# Open-field photovoltaic power plant
if param_value['PV_area_field'] > 0:
    energysystem.add(
            solph.Source(label='PV_field',
                         outputs={bel: solph.Flow(
                                 actual_value=(data['Sol_irradiation [Wh/sqm]'] * param_value['eta_PV'] * 0.000001),  # [MWh/m²]
                                 nominal_value=param_value['PV_area_field']*10000,  # [m²]
                                 fixed=True)})
                        )

# Rooftop photovoltaic
if param_value['PV_area_roof'] > 0:    
    energysystem.add(
            solph.Source(label='PV_roof',
                         outputs={bel: solph.Flow(
                                 actual_value=(data['Sol_irradiation [Wh/sqm]'] * param_value['eta_PV'] * 0.000001),  # [MWh/m²]
                                 nominal_value=param_value['PV_area_roof']*10000,  # [m²]
                                 fixed=True)})
                    )

# Rooftop solar thermal
if param_value['area_solar_th'] > 0:    
    energysystem.add(
            solph.Source(label='solar_thermal',
                         outputs={bth: solph.Flow(
                                 actual_value=(data['Sol_irradiation [Wh/sqm]'] * param_value['eta_solar_th'] * 0.000001),  # [MWh/m²]
                                 nominal_value=param_value['area_solar_th']*10000,  # [m²]
                                 fixed=True)})
                    )

# Combined heat and power plant
if param_value['number_of_chps'] > 0:
    energysystem.add(
            solph.Transformer(label='chp',
                              inputs={bgas: solph.Flow()},
                              outputs={bth: solph.Flow(
                                      nominal_value=param_value['number_of_chps']*param_value['chp_heat_output']),  # [MW]
                                       bel: solph.Flow()},
                              conversion_factors={bth: param_value['conversion_factor_bth_chp'],
                                                  bel: param_value['conversion_factor_bel_chp']})
                    )

# Boiler
if param_value['number_of_boilers'] > 0:
    energysystem.add(
            solph.Transformer(label='boiler',
                              inputs={bgas: solph.Flow()},
                              outputs={bth: solph.Flow(
                                      nominal_value=param_value['number_of_boilers']*param_value['boiler_heat_output'])},   # [MWh]
                              conversion_factors={bth: param_value['conversion_factor_boiler']})
                    )   
            
# Heat pump
if param_value['number_of_heat_pumps'] > 0:
    energysystem.add(
            solph.Transformer(label='heat_pump',
                              inputs={bel: solph.Flow()},
                              outputs={bth: solph.Flow(
                                      nominal_value=(param_value['number_of_heat_pumps'] * param_value['heatpump_heat_output']))},  # [MW]
                              conversion_factors={bth: param_value['COP_heat_pump']})
                    )


# Thermal storage
if param_value['capacity_thermal_storage'] > 0:   
    energysystem.add(
            solph.components.GenericStorage(nominal_storage_capacity=(param_value['capacity_thermal_storage'] * param_value['daily_demand_th']),
                                            label='storage_th',
                                            inputs={bth: solph.Flow(
                                                         nominal_value=(param_value['capacity_thermal_storage']
                                                         * param_value['daily_demand_th'] / param_value['charge_time_storage_th']))},
                                             outputs={bth: solph.Flow(
                                                          nominal_value=(param_value['capacity_thermal_storage']
                                                          * param_value['daily_demand_th'] / param_value['charge_time_storage_th']))},
                                             loss_rate=param_value['capacity_loss_storage_th'],
                                             initial_storage_level=param_value['init_capacity_storage_th'],
                                             inflow_conversion_factor=param_value['inflow_conv_factor_storage_th'],
                                             outflow_conversion_factor=param_value['outflow_conv_factor_storage_th'])
                      )

# Electricty storage
if param_value['capacity_electr_storage'] > 0:
    energysystem.add(
            solph.components.GenericStorage(nominal_storage_capacity=(param_value['capacity_electr_storage'] * param_value['daily_demand_el']),
                                            label='storage_el',
                                            inputs={bel: solph.Flow(
                                                        nominal_value=(param_value['capacity_electr_storage']
                                                        * param_value['daily_demand_el'] / param_value['charge_time_storage_el']))},
                                            outputs={bel: solph.Flow(
                                                        nominal_value=(param_value['capacity_electr_storage']
                                                        * param_value['daily_demand_el'] / param_value['charge_time_storage_el']))},
                                            loss_rate=param_value['capacity_loss_storage_el'],
                                            initial_storage_level=param_value['init_capacity_storage_el'],
                                            inflow_conversion_factor=param_value['inflow_conv_factor_storage_el'],
                                            outflow_conversion_factor=param_value['outflow_conv_factor_storage_el'])
                    )


##########################################################################
# Optimise the energy system and plot the results
##########################################################################

logging.info('Optimise the energy system')

model = solph.Model(energysystem)

if cfg['debug']:
    filename = os.path.join(
        helpers.extend_basic_path('lp_files'), 'model.lp')
    logging.info('Store lp-file in {0}.'.format(filename))
    model.write(filename, io_options={'symbolic_solver_labels': True})

# if tee_switch is true solver messages will be displayed
logging.info('Solve the optimization problem')
model.solve(solver=cfg['solver'], solve_kwargs={'tee': cfg['solver_verbose']})

logging.info('Store the energy system with the results.')

energysystem.results['main'] = outputlib.processing.results(model)
energysystem.results['meta'] = outputlib.processing.meta_results(model)

energysystem.dump(dpath=abs_path + "/results/optimisation_results/dumps",
                  filename="model.oemof")


#########################################################################
# Analyse results
#########################################################################

energysystem = solph.EnergySystem()

abs_path = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
energysystem.restore(dpath=abs_path + "/results/optimisation_results/dumps",
                     filename="model.oemof")

results = energysystem.results
string_results = outputlib.views.convert_keys_to_strings(
                energysystem.results['main'])

## Call main analysis function
results_main = display_results(string_results, param_value)

#########################################################################
# Detailed analysis
#########################################################################
start = 0
end = 1400


plot_results_elec(string_results, param_value, data, start, end)
plot_results_heat(string_results, param_value, data, start, end)
plot_results_ressources(string_results, param_value, data, start, end)
