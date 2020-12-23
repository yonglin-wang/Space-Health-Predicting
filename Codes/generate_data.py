import os             
import glob
import pandas as pd
import numpy as np
import scipy as sp
from scipy.interpolate import interp1d
from datetime import timedelta
# import matplotlib.pyplot as plt
import warnings
from pandas.core.common import SettingWithCopyWarning
warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)

####### define my own sliding window function
def sliding_window(data, buck_size, step):
    list_all = []
    temp_len = len(data[data.between(data.iloc[0], data.iloc[0] + buck_size)])
    for i in range(len(data)): 
        left = data.iloc[i] + i * step 
        right = data.iloc[i] + i * step  + buck_size
        series1 = data[data.between(left, right)] 
        if len(series1)<2:
            continue
        if data.iloc[-1] - left < 0.5:
            break 
        list_all.append(series1)
    return list_all



def generate_features(time_scale_train = 0.5,
    time_ahead = 0.5,
    sampling_rate = 50,
    time_gap=3,
    time_step = 0.3):
    np.set_printoptions(suppress=True)

    for_names = str(int(time_ahead*1000))

    data_all = pd.read_csv('data/data_all.csv')
    
    ##### extract all needed columns ######
    neededCols = ['seconds','trialPhase','currentPosRoll','currentVelRoll','calculated_vel',\
                'joystickX', 'peopleName', 'trialName', 'peopleTrialKey', 'datetimeNew']

    data_needed = data_all[neededCols]
    data_needed['datetimeNew'] = pd.to_datetime(data_needed['datetimeNew'])
    data_needed = data_needed[data_needed.trialPhase!=1]
    data_needed.set_index('datetimeNew', inplace =True)

    ##### define crash event by trialPhase 
    crashed_on_trialPhase = data_needed[data_needed.trialPhase==4]

    ##### excluding the trialPhase=1 and the left are human being behavior 
    crashed_on_trialPhase = crashed_on_trialPhase[crashed_on_trialPhase.trialPhase!=1]

    ###### use the data based on trialPhase and get all the unique peopleTrialKey has a crash
    crash_event = crashed_on_trialPhase
    peopleTrialHasCrash = crash_event.peopleTrialKey.unique()

    ####### give a threshold of a time interval between two consecutive crashes within one trial #######  
    crash_excludeShortT = pd.DataFrame()
    for x in range(len(peopleTrialHasCrash)):
        trial = peopleTrialHasCrash[x]
        df = crash_event[crash_event.peopleTrialKey == trial]
        df['seconds_shift'] = df['seconds'].shift(1)
        df.fillna(0, inplace=True)
        df['time_gap'] = df['seconds'] - df['seconds_shift']
        # now we try to set as 2 seconds as a short-time crash
        df = df[df.time_gap > time_gap]
        crash_excludeShortT = pd.concat([crash_excludeShortT, df])


    
    crash_feature_label_300ms_500ms_test = pd.DataFrame()
    peopleTrialHasCrash_ex = crash_excludeShortT.peopleTrialKey.unique()
    for num in range(len(peopleTrialHasCrash)):
        j = peopleTrialHasCrash[num]
        print(num)
        for i in (crash_excludeShortT.loc[
                            ((crash_excludeShortT['peopleTrialKey'] == j)),'seconds']):
            
            temp_df = pd.concat([data_needed[(data_needed.seconds <= i - time_ahead) &\
                            (data_needed.seconds >= i - time_scale_train - time_ahead) \
                        &(data_needed['peopleTrialKey'] == j)]]) 
            
            ##### resample & interpolate
            temp_df = temp_df[['seconds', 'currentVelRoll','currentPosRoll','calculated_vel','joystickX','peopleTrialKey']]
            x = temp_df.seconds
            y_calculated_vel = temp_df.calculated_vel
            y_org_vel = temp_df.currentVelRoll
            y_currentPosRoll = temp_df.currentPosRoll
            y_joystickX = temp_df.joystickX
            
            
            new_x = np.linspace(x.min(), x.max(), sampling_rate)
            new_y_calculated_vel = sp.interpolate.interp1d(x, y_calculated_vel, kind='linear')(new_x)
            new_y_original_vel = sp.interpolate.interp1d(x, y_org_vel, kind='linear')(new_x)
            new_y_currentPosRoll = sp.interpolate.interp1d(x, y_currentPosRoll, kind='linear')(new_x)
            new_y_joystickX = sp.interpolate.interp1d(x, y_joystickX, kind='linear')(new_x)
            
            

            arr1 = np.dstack([new_y_calculated_vel, new_y_currentPosRoll, new_y_joystickX]).reshape(sampling_rate,3)
            arr2 = np.dstack([new_y_original_vel, new_y_currentPosRoll, new_y_joystickX]).reshape(sampling_rate,3)
            arr3 = 1
            arr4 = temp_df['peopleTrialKey'].iloc[0]
            arr5 = temp_df['seconds'].iloc[0]
            arr6 = temp_df['seconds'].iloc[-1]
            
            crash_feature_label_300ms_500ms_test = pd.concat(\
                                [crash_feature_label_300ms_500ms_test, pd.DataFrame([[arr1, arr2, arr3, arr4, arr5, arr6]],\
                                columns=["features_cal_vel","features_org_vel",'label', 'peopleTrialKey', 'start_seconds', 'end_seconds']) ])   


    crash_feature_label_300ms_500ms_test.to_pickle('data/'+ 'crash_feature_label_'+ for_names+ 'ms' + '_500ms_test')



    
    ####### crash event data info with features within 0.5 second previous data ######
    # time_scale_train = 0.5
    # time_ahead = 0.3
    # time_step = 0.3
    # sampling_rate = 50
    peopleTrialHasCrash_ex = crash_excludeShortT.peopleTrialKey.unique()

    noncrash_feature_label_300ms_500ms_test = pd.DataFrame()
    for num in range(len(peopleTrialHasCrash_ex)):
        j = peopleTrialHasCrash_ex[num]
        print(num) 
        df = crash_excludeShortT[crash_excludeShortT.peopleTrialKey == j]
        df['seconds_shift'] = df['seconds'].shift(1)
        df.fillna(0, inplace=True)
        df['time_gap'] = df['seconds'] - df['seconds_shift']
        
        df_trial = data_needed[(data_needed['peopleTrialKey'] == j)]

        for i in (crash_excludeShortT.loc[
                            (crash_excludeShortT['peopleTrialKey'] == j),'seconds']):
            left = df.seconds_shift[df.seconds==i].iloc[0] 
            right = i - time_scale_train - time_ahead
            noncrash_time_range = [left, right]

            temp_serie = df_trial.loc[(df_trial.seconds>=left) & (df_trial.seconds<=right) \
                              ,'seconds'] 
            
            
            list_all = sliding_window(temp_serie, time_scale_train, time_step) 

            print('====================', len(list_all))
            print('----------------------', len(list_all[0]))
            print('xxxxxxxxxxxxxxxxxx', len(list_all[1]))

            
            for x in range(len(list_all)):
                temp_df = df_trial[(df_trial.seconds >= list_all[x].iloc[0])\
                            & (df_trial.seconds <= list_all[x].iloc[-1])]
        
                ##### resample & interpolate
                temp_df = temp_df[['seconds', 'currentVelRoll', 'currentPosRoll','calculated_vel','joystickX','peopleTrialKey']]
                x = temp_df.seconds
                y_calculated_vel = temp_df.calculated_vel
                y_org_vel = temp_df.currentVelRoll
                y_currentPosRoll = temp_df.currentPosRoll
                y_joystickX = temp_df.joystickX

                new_x = np.linspace(x.min(), x.max(), sampling_rate)
                new_y_calculated_vel = sp.interpolate.interp1d(x, y_calculated_vel, kind='linear')(new_x)
                new_y_original_vel = sp.interpolate.interp1d(x, y_org_vel, kind='linear')(new_x)
                new_y_currentPosRoll = sp.interpolate.interp1d(x, y_currentPosRoll, kind='linear')(new_x)
                new_y_joystickX = sp.interpolate.interp1d(x, y_joystickX, kind='linear')(new_x)



                arr11 = np.dstack([new_y_calculated_vel, new_y_currentPosRoll, new_y_joystickX]).reshape(sampling_rate,3)
                arr22 = np.dstack([new_y_original_vel, new_y_currentPosRoll, new_y_joystickX]).reshape(sampling_rate,3)
                arr33 = 0
                arr44 = temp_df['peopleTrialKey'].iloc[0]
                arr55 = temp_df['seconds'].iloc[0]
                arr66 = temp_df['seconds'].iloc[-1]
            
                noncrash_feature_label_300ms_500ms_test = pd.concat(\
                                [noncrash_feature_label_300ms_500ms_test, pd.DataFrame([[arr11, arr22, arr33, arr44, arr55, arr66]],\
                                columns=["features_cal_vel","features_org_vel",'label', 'peopleTrialKey', 'start_seconds', 'end_seconds']) ]) 


    noncrash_feature_label_300ms_500ms_test.to_pickle('data/'+ 'noncrash_feature_label_'+ for_names+ 'ms' + '_500ms_test')

if __name__ == "__main__":
    generate_features(time_scale_train = 0.5,
    time_ahead = 0.5,
    sampling_rate = 50,
    time_gap=3,
    time_step = 0.3)