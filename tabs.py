'''
Read in data that is served through TABS website.
'''

import pandas as pd


def read_tabs(buoy, dstart, dend, tz='UTC'):
    '''Read in data for TABS buoy. Return dataframe.

    buoy: string containing buoy name
    dstart: string containing start date and time
    dend: string containing end date and time
    tz: 'UTC' by default but could also be 'US/Central'

    Note that data are resampled to be every 30 minutes to have a single dataframe.
    '''

    # use pandas Timestamp functionality to interpret input datetimes
    dstart = pd.Timestamp(dstart)
    dend = pd.Timestamp(dend)

    df = pd.DataFrame()
    for table in ['met', 'salt', 'ven', 'wave']:
        # table = 'met'
        url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&table=' + table + '&Datatype=download&units=M&tz=' + tz + '&model=False&datepicker='
        url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
        try:  # not all buoys have all datasets
            dfnew = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999)[dstart:dend].tz_localize(tz)
            df = pd.concat([df, dfnew], axis=1)
        except:
            pass

    return df


def read_other(buoy, dstart, dend, tz='UTC'):
    '''Read in data for non-TABS buoy. Return dataframe.

    buoy: string containing buoy name
    dstart: string containing start date and time
    dend: string containing end date and time
    tz: 'UTC' by default but could also be 'US/Central'

    Note that data are resampled to be every 30 minutes to have a single dataframe.
    '''

    pass

    # # use pandas Timestamp functionality to interpret input datetimes
    # dstart = pd.Timestamp(dstart)
    # dend = pd.Timestamp(dend)
    #
    # df = pd.DataFrame()
    # for table in ['met', 'salt', 'ven', 'wave']:
    #     # table = 'met'
    #     url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&table=' + table + '&Datatype=download&units=M&tz=' + tz + '&model=False&datepicker='
    #     url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
    #     try:  # not all buoys have all datasets
    #         dfnew = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999)[dstart:dend].tz_localize(tz)
    #         df = pd.concat([df, dfnew], axis=1)
    #     except:
    #         pass
    #
    # return df


def read_twdb():
    pass

def read_usgs():
    pass
