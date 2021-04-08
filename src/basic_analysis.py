"""
Created on Thu Jan  10 12:32:01 2020

@author: Daniel
"""

###############################################################################
# imports
###############################################################################
import oemof.solph as solph
import oemof.outputlib as outputlib
import oemof.tools.economics as eco

import os
import pandas as pd
import yaml

import matplotlib.pyplot as plt
import numpy as np

def display_results(string_results, param_value):

    # Extract specific time series (sequences) from results data
    shortage_electricity = string_results[
        'shortage_bel', 'electricity']['sequences']
    shortage_heat = string_results[
        'shortage_bth', 'heat']['sequences']
    gas_consumption = string_results[
        'rgas', 'natural_gas']['sequences']
    heat_demand = string_results[
        'heat', 'demand_th']['sequences']
    el_demand = string_results[
        'electricity', 'demand_el']['sequences']

    print("")
    print('-- Results --')
    #print(shortage_electricity.sum())
    #print(shortage_heat.sum())
    #print(gas_consumption.sum())
    #print(heat_demand.sum())
    #print(el_demand.sum())
    ###########################################################################
    # CO2-Emissions
    ###########################################################################
    em_co2 = (gas_consumption.flow.sum()
              *param_value['emission_gas']
             + shortage_electricity.flow.sum()
              *param_value['emission_el']
             + shortage_heat.flow.sum()
              *param_value['emission_heat'])  # [(MWh/a)*(kg/MWh)]
    print("CO2-Emission: {:.2f}".format(em_co2/1000), "t/a")

    ###########################################################################
    # Costs
    ###########################################################################
    capex_chp = (param_value['number_of_chps']
                 * param_value['invest_cost_chp'])
    capex_boiler = (param_value['number_of_boilers']
                    * param_value['invest_cost_boiler'])
    capex_wind = (param_value['number_of_windturbines']
                  * param_value['invest_cost_wind'])
    capex_hp = (param_value['number_of_heat_pumps']
                * param_value['invest_cost_heatpump'])
    capex_storage_el = (param_value['capacity_electr_storage']
                        * param_value['invest_cost_storage_el'])
    capex_storage_th = (param_value['capacity_thermal_storage']
                        * param_value['invest_cost_storage_th'])
    capex_pv_roof = param_value['PV_area_roof'] * param_value['invest_cost_pv']
    capex_solarthermal = (param_value['area_solar_th']
                          * param_value['invest_cost_solarthermal'])
    capex_pv_field = (param_value['PV_area_field'] * param_value['invest_cost_PV_pp'])

    # Calculate annuity of each technology
    annuity_chp = eco.annuity(
        capex_chp,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_boiler = eco.annuity(
        capex_boiler,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_wind = eco.annuity(
        capex_wind,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_hp = eco.annuity(
        capex_hp,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_storage_el = eco.annuity(
        capex_storage_el,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_storage_th = eco.annuity(
        capex_storage_th,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_pv_roof = eco.annuity(
        capex_pv_roof,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_solar_th = eco.annuity(
        capex_solarthermal,
        param_value['lifetime'],
        param_value['wacc'])
    annuity_pv_field = eco.annuity(
        capex_pv_field,
        param_value['lifetime'],
        param_value['wacc'])


    # Variable costs
    var_costs_gas = gas_consumption.flow.sum()*param_value['var_costs_gas']
    var_costs_el_import = (shortage_electricity.flow.sum()
                           * param_value['var_costs_shortage_bel'])
    var_costs_heat_import = (shortage_heat.flow.sum()
                             * param_value['var_costs_shortage_bth'])
    var_costs_es = var_costs_gas + var_costs_el_import + var_costs_heat_import

    total_annuity = (annuity_chp + annuity_boiler + annuity_wind
                     + annuity_hp + annuity_storage_el
                     + annuity_storage_th + annuity_pv_roof
                     + annuity_solar_th + annuity_pv_field)

    print("Total Costs of Energy System per Year: {:.2f}".format(
        (var_costs_es+total_annuity) / 1e6), "Mio. €/a")

    ###########################################################################
    # Self-Sufficiency
    ###########################################################################

    # Take electrical consumption of heat pump (hp) into account. Quantity of
    # 'el_demand' does not include electrical consumption of hp.
    if param_value['number_of_heat_pumps'] > 0:
        el_consumption_hp = string_results[
            'electricity', 'heat_pump']['sequences'].flow.sum()
        el_consumption_incl_heatpump = el_demand.flow.sum() + el_consumption_hp
        coverage_el = ((el_consumption_incl_heatpump
                        - shortage_electricity.flow.sum())
                       / el_consumption_incl_heatpump)
    else:
        coverage_el = ((el_demand.flow.sum() - shortage_electricity.flow.sum())
                       / el_demand.flow.sum())

    coverage_heat = ((heat_demand.flow.sum() - shortage_heat.flow.sum())
                     / heat_demand.flow.sum())
    selfsufficiency = (coverage_el + coverage_heat) / 2

    print("Self-Sufficiency: {:.2f} %".format(selfsufficiency*100))
    print("")

    return [(em_co2/1e3), ((var_costs_es+total_annuity)/1e6), (selfsufficiency*100)],[(em_co2/1e3), (em_co2/1e3)+10000, 
             ((var_costs_es+total_annuity)/1e6), ((var_costs_es+total_annuity)/1e6)+10000, 
             (selfsufficiency*100), (selfsufficiency*100)-100]




def plot_results_elec(string_results, param_value, data, start, end):
    print("")
    print('-- Plotting electricty --')
    
    set_alpha = 1.
    bar_width = 0.9
    
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10,5) , sharey=True,sharex=False)
    plt.subplots_adjust(wspace=0.25, hspace=0.05)
    
    if param_value['number_of_chps'] > 0:
        elec_chp = string_results['chp', 'electricity']['sequences']['flow'][start:end]
    else:
        elec_chp = np.zeros(len(data['Demand_el [MWh]'][start:end])) 
    
    if param_value['number_of_windturbines'] > 0:
        elec_wind = string_results['wind_turbine', 'electricity']['sequences']['flow'][start:end]
    else:
        elec_wind = np.zeros(len(data['Demand_el [MWh]'][start:end]))        
    
    if param_value['PV_area_field'] > 0:
        elec_pv_frei = string_results['PV_field', 'electricity']['sequences']['flow'][start:end]
    else:
        elec_pv_frei = np.zeros(len(data['Demand_el [MWh]'][start:end]))        
    
    if param_value['PV_area_roof'] > 0:
        elec_pv = string_results['PV_roof', 'electricity']['sequences']['flow'][start:end]
    else:
        elec_pv = np.zeros(len(data['Demand_el [MWh]'][start:end]))

    if param_value['capacity_electr_storage'] > 0:
        storage_el_cap = string_results['storage_el', 'None']['sequences']['capacity'][start:end]
    else:
        storage_el_cap = np.zeros(len(data['Demand_el [MWh]'][start:end]))
        
    axes[0].bar(np.arange(len(elec_chp)), elec_chp, 
               width=bar_width, alpha=set_alpha, color='green', label='BHKW')

    axes[0].bar(np.arange(len(elec_wind)), elec_wind, 
              bottom=elec_chp, width=bar_width, alpha=set_alpha, color='blue', label='Wind')
    
    axes[0].bar(np.arange(len(elec_pv)), elec_pv, 
               bottom=elec_chp+elec_wind+elec_pv_frei, width=bar_width, alpha=set_alpha, color='red', label='PV Dach')

    axes[0].bar(np.arange(len(elec_pv_frei)), elec_pv_frei, 
              bottom=elec_chp+elec_wind, width=bar_width, alpha=set_alpha, color='gold', label='PV Freifl.')

        
    axes[0].plot(np.arange(0,len(data['Demand_el [MWh]'][start:end])), data['Demand_el [MWh]'][start:end], 
             alpha=0.75, color='magenta', label='Strombedarf')
    
    axes[0].set_ylim(0,25)
    axes[0].set_ylabel('Energie Elektrizität [MWh]')
    #ax1.tick_params(axis='y', labelcolor=color1)
    axes[0].set_xlabel('Jahresstunden [h]')
    axes[0].legend()
    axes[0].grid()
    
    elec_shortage = string_results['shortage_bel', 'electricity']['sequences']['flow'][start:end]
    axes[1].plot(np.arange(len(elec_shortage)), elec_shortage, 
                  alpha=0.75, color='cyan', label='Elektrizität Fehlmenge')
    
    elec_excess = string_results['electricity', 'excess_bel']['sequences']['flow'][start:end]
    axes[1].plot(np.arange(len(elec_excess)), elec_excess, 
                  alpha=0.75, color='darkcyan', label='Elektrizität Überschuss')

    #axes[1].plot(np.arange(len(storage_el_cap)), storage_el_cap, 
    #              alpha=0.75, color='red', label='El. Speicher')    
    
    axes[1].set_xlabel('Jahresstunden [h]')
    axes[1].legend()
    axes[1].grid()
    
    plt.show()
    
    abs_path = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
    fig.savefig(abs_path + '/results/detailed_analysis_elec.png', dpi=300, facecolor='w', edgecolor='w',
        orientation='portrait', papertype=None, format=None,
        transparent=False, bbox_inches=None, pad_inches=0.1, frameon=None, metadata=None)

    
def plot_results_heat(string_results, param_value, data, start, end):    
    set_alpha = 1.
    bar_width = 0.9
    
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10,5) , sharey=True,sharex=False)
    plt.subplots_adjust(wspace=0.25, hspace=0.05)
    
    if param_value['number_of_chps'] > 0:
        heat_chp = string_results['chp', 'heat']['sequences']['flow'][start:end]
    else:
        heat_chp = np.zeros(len(data['Demand_th [MWh]'][start:end]))
        
    if param_value['number_of_heat_pumps'] > 0:
        heat_heat_pump = string_results['heat_pump', 'heat']['sequences']['flow'][start:end]
    else:
        heat_heat_pump = np.zeros(len(data['Demand_th [MWh]'][start:end]))
    
    if param_value['number_of_boilers'] > 0:
        heat_boilers = string_results['boiler', 'heat']['sequences']['flow'][start:end]
    else:
        heat_boilers = np.zeros(len(data['Demand_th [MWh]'][start:end]))
        
    if param_value['area_solar_th'] > 0:
        heat_solar = string_results['solar_thermal', 'heat']['sequences']['flow'][start:end]
    else:
        heat_solar =  np.zeros(len(data['Demand_th [MWh]'][start:end]))
    
    axes[0].bar(np.arange(len(heat_chp)), heat_chp, 
                   width=bar_width, alpha=set_alpha, color='green', label='chp')
    axes[0].bar(np.arange(len(heat_heat_pump)), heat_heat_pump, 
                  bottom=heat_chp, width=bar_width, alpha=set_alpha, color='blue', label='Wärmepumpe')
    axes[0].bar(np.arange(len(heat_boilers)), heat_boilers, 
                  bottom=heat_chp+heat_heat_pump, width=bar_width, alpha=set_alpha, color='gold', label='Heizkessel')
    axes[0].bar(np.arange(len(heat_solar)), heat_solar, 
                  bottom=heat_chp+heat_heat_pump+heat_boilers, width=bar_width, alpha=set_alpha, color='red', label='Solarthermie')
        
                
    axes[0].plot(np.arange(0,len(data['Demand_th [MWh]'][start:end])), data['Demand_th [MWh]'][start:end], 
             alpha=0.75, color='magenta', label='Wärmebedarf')
    
    axes[0].set_ylim(0,40)
    axes[0].set_ylabel('Energie Wärme [MWh]')
    #ax1.tick_params(axis='y', labelcolor=color1)
    axes[0].set_xlabel('Jahresstunden [h]')
    axes[0].legend()
    axes[0].grid()
    
    
    heat_shortage = string_results['shortage_bth', 'heat']['sequences'][start:end]['flow']
    axes[1].plot(np.arange(len(heat_shortage)), heat_shortage, 
                  alpha=0.75, color='cyan', label='Wärme Fehlmenge')
    
    heat_excess = string_results['heat', 'excess_bth']['sequences'][start:end]['flow']
    axes[1].plot(np.arange(len(heat_excess)), heat_excess, 
                  alpha=0.75, color='darkcyan', label='Wärme Überschusss')
    
    axes[1].set_xlabel('Jahresstunden [h]')
    axes[1].legend()
    axes[1].grid()
    
    plt.show()
    abs_path = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
    fig.savefig(abs_path + '/results/detailed_analysis_heat.png', dpi=300, facecolor='w', edgecolor='w',
        orientation='portrait', papertype=None, format=None,
        transparent=False, bbox_inches=None, pad_inches=0.1, frameon=None, metadata=None)
    

## Ressources        
def plot_results_ressources(string_results, param_value, data, start, end):
   
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10,5) , sharey=True,sharex=False)
    plt.subplots_adjust(wspace=0.25, hspace=0.05)
    
    if param_value['number_of_heat_pumps'] > 0:    
        elec_heat_pump = string_results['electricity', 'heat_pump']['sequences']['flow'][start:end]
        axes[0].plot(np.arange(len(elec_heat_pump)), elec_heat_pump, 
                  alpha=0.75, color='lightskyblue', label='elec heat pump') 
    
    axes[0].set_ylim(0,20)
    axes[0].set_ylabel('Arbeit [MWh]')
    axes[0].set_xlabel('Jahresstunden [h]')
    axes[0].legend()
    axes[0].grid()

    if param_value['number_of_boilers'] > 0 or param_value['number_of_chps'] > 0:
        gas = string_results['rgas', 'natural_gas']['sequences']['flow'][start:end]
        axes[1].plot(np.arange(len(gas)), gas, 
                  alpha=0.75, color='gold', label='natural gas')
    axes[1].set_xlabel('Jahresstunden [h]')
    axes[1].legend()
    axes[1].grid()
        
    plt.show()        
    abs_path = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
    fig.savefig(abs_path + '/results/detailed_analysis_ressources.png', dpi=300, facecolor='w', edgecolor='w',
        orientation='portrait', papertype=None, format=None,
        transparent=False, bbox_inches=None, pad_inches=0.1, frameon=None, metadata=None)
        