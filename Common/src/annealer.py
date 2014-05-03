'''
Created on May 3, 2014

@author: Vince (dev)
'''

from random import random
from math import exp

class Annealer(object):
    @staticmethod
    def anneal(initial_state, move_func, objective_func, k, schedule_temps, schedule_times):
        '''
        move_func := the function that moves the target from one point in the state-space to another
        objective_fun := the objective function that returns an energy E
        k := the constant that sets probability of acceptance for some energy E and some temperature T0
        schedule_temps := a list of temperatures to anneal at
        schedule_times := a list of durations to anneal at each temperature
        '''
        best_energy = objective_func(initial_state)
        best_state = initial_state.copy()
        prev_state = initial_state.copy()
        prev_energy = best_energy
        for step in range(len(schedule_temps)):
            temp = schedule_temps[step]
            time = schedule_times[step]
            for t in range(time):
                state = move_func(prev_state)
                energy = objective_func(state)
                delta_energy = energy-prev_energy
                # accept the new state if lower energy or probabilistically
                if energy < prev_energy:
                    prev_energy = energy
                    prev_state = state.copy()
                    if energy < best_energy:
                        best_energy = energy
                        best_state = state.copy()
                elif random() < exp(-delta_energy/(k*temp)):
                    prev_energy = energy
                    prev_state = state.copy()
        return best_state
    
    @staticmethod
    def configureLinearSchedule(min_temp, max_temp, min_time, max_time, time_step):
        times = list(range(max_time, min_time, -time_step))
        temp_step = (max_temp - min_temp)/len(times)
        temps = [min_temp+temp_step*i for i in range(len(times))]
        return (temps, times)